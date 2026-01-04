#include <sys/types.h>
#include <sys/socket.h>
#include <sys/epoll.h>
#include <sys/timerfd.h>
#include <netinet/in.h>
#include <arpa/inet.h>
#include <unistd.h>
#include <fcntl.h>

#include <cstring>
#include <cstdlib>
#include <iostream>
#include <sstream>
#include <unordered_map>
#include <unordered_set>
#include <vector>
#include <deque>
#include <map>
#include <set>
#include <algorithm>
#include <random>
#include <chrono>
#include <cmath>

using namespace std;

static const int MAX_EVENTS = 64;
static const int BUFFER_LIMIT = 4096;

int make_socket_non_blocking(int sfd) {
    int flags = fcntl(sfd, F_GETFL, 0);
    if (flags == -1) return -1;
    flags |= O_NONBLOCK;
    if (fcntl(sfd, F_SETFL, flags) == -1) return -1;
    return 0;
}

string trim(const string &s) {
    size_t a = 0;
    while (a < s.size() && isspace((unsigned char)s[a])) a++;
    size_t b = s.size();
    while (b > a && isspace((unsigned char)s[b-1])) b--;
    return s.substr(a, b-a);
}

vector<string> split(const string &s, char delim) {
    vector<string> out;
    string cur;
    for (char c : s) {
        if (c == delim) { out.push_back(cur); cur.clear(); }
        else cur.push_back(c);
    }
    out.push_back(cur);
    return out;
}

string join(const vector<string>& parts, char delim) {
    string out;
    for (size_t i=0;i<parts.size();++i) {
        if (i) out.push_back(delim);
        out += parts[i];
    }
    return out;
}

string gen_code(int len=6) {
    static const char* chars = "ABCDEFGHJKMNPQRSTUVWXYZ23456789"; 
    static random_device rd;
    static mt19937_64 gen(rd());
    uniform_int_distribution<int> dist(0, (int)strlen(chars)-1);
    string s;
    for (int i=0;i<len;i++) s.push_back(chars[dist(gen)]);
    return s;
}

struct Client;
struct Quiz;

struct Question {
    string text;
    vector<string> opts;
    int correct_index;
    int points;
    int time_limit; // seconds
};

enum Role { ROLE_NONE, ROLE_CREATOR, ROLE_PLAYER };
enum Phase { PHASE_QUESTION, PHASE_REVEAL };

struct Client {
    int fd;
    string inbuf;
    deque<string> outbuf;
    string nick;
    Role role = ROLE_NONE;
    string quiz_code;
    bool closed = false;
};

struct Quiz {
    string code;
    int creator_fd;
    vector<Question> questions;
    bool started = false;
    size_t current_q = 0;
    // players: set of player fds (connected clients) in this quiz
    set<int> players;
    // scoreboard stored by nick => points
    map<string,int> scores; // note: keep nick even if player disconnects
    // per-question responses: nick -> answer_index
    map<string,int> responses;
    // timerfd for current question or reveal pause; -1 if none
    int timerfd = -1;
    // number of participants at start of current question (used for 2/3 rule)
    int participants_for_threshold = 0;
    // phase: whether we're showing question or in reveal pause
    Phase phase = PHASE_QUESTION;
};

unordered_map<int, Client> clients; // fd -> client
unordered_map<string, Quiz> quizzes; // code -> quiz
unordered_map<string,int> nick2fd; // nick -> fd (active connections only)
int epollfd_global = -1;
int listenfd_global = -1;

void modify_epoll_out(int fd, bool want_out) {
    struct epoll_event ev;
    ev.events = EPOLLIN | (want_out ? EPOLLOUT : 0U);
    ev.data.fd = fd;
    if (epoll_ctl(epollfd_global, EPOLL_CTL_MOD, fd, &ev) == -1) {
        if (epoll_ctl(epollfd_global, EPOLL_CTL_ADD, fd, &ev) == -1) {
            // ignore errors for closed fds
        }
    }
}

void queue_send(Client &c, const string &msg) {
    c.outbuf.push_back(msg + "\n");
    modify_epoll_out(c.fd, true);
}

void close_client(int fd);

unordered_map<int,string> timerfd2quiz; // timerfd -> quiz_code

void broadcast_to_quiz(const Quiz &q, const string &msg, bool to_creator=true, bool to_players=true) {
    // send to creator
    if (to_creator) {
        auto itc = clients.find(q.creator_fd);
        if (itc != clients.end()) {
            queue_send(itc->second, msg);
        }
    }
    if (to_players) {
        for (int pfd : q.players) {
            auto it = clients.find(pfd);
            if (it != clients.end()) {
                queue_send(it->second, msg);
            }
        }
    }
}

void send_lobby_update(Quiz &q) {
    vector<string> nicks;
    auto itc = clients.find(q.creator_fd);
    if (itc != clients.end()) {
        if (!itc->second.nick.empty()) nicks.push_back(itc->second.nick + "(host)");
    }
    for (int pfd : q.players) {
        auto it = clients.find(pfd);
        if (it != clients.end()) {
            if (!it->second.nick.empty()) nicks.push_back(it->second.nick);
        }
    }
    string list = join(nicks, ',');
    string msg = string("LOBBY_PLAYERS|") + list;
    broadcast_to_quiz(q, msg, true, true);
}

void close_client(int fd) {
    auto it = clients.find(fd);
    if (it == clients.end()) return;
    Client &c = it->second;
    // If client had nick, remove from nick map
    if (!c.nick.empty()) {
        auto nit = nick2fd.find(c.nick);
        if (nit != nick2fd.end() && nit->second == fd) nick2fd.erase(nit);
    }
    // If client was part of a quiz, handle disconnect logic
    if (!c.quiz_code.empty()) {
        auto qit = quizzes.find(c.quiz_code);
        if (qit != quizzes.end()) {
            Quiz &q = qit->second;
            if (c.role == ROLE_CREATOR) {
                if (!q.started) {
                    // creator disconnected before start -> remove quiz and inform players
                    for (int pfd : q.players) {
                        if (clients.count(pfd)) {
                            queue_send(clients[pfd], "QUIZ_CANCELLED");
                            clients[pfd].quiz_code.clear();
                        }
                    }
                    // remove quiz
                    if (q.timerfd != -1) {
                        epoll_ctl(epollfd_global, EPOLL_CTL_DEL, q.timerfd, nullptr);
                        timerfd2quiz.erase(q.timerfd);
                        close(q.timerfd);
                    }
                    quizzes.erase(qit);
                } else {
                    // creator disconnected after start -> abort quiz
                    for (int pfd : q.players) {
                        if (clients.count(pfd)) {
                            queue_send(clients[pfd], "QUIZ_ABORTED");
                            clients[pfd].quiz_code.clear();
                        }
                    }
                    if (q.timerfd != -1) {
                        epoll_ctl(epollfd_global, EPOLL_CTL_DEL, q.timerfd, nullptr);
                        timerfd2quiz.erase(q.timerfd);
                        close(q.timerfd);
                    }
                    quizzes.erase(qit);
                }
            } else if (c.role == ROLE_PLAYER) {
                // remove player from quiz players set
                q.players.erase(fd);
                // keep their score in table (score map keyed by nick)
                if (!q.started) {
                    send_lobby_update(q);
                }
            }
        }
    }

    // remove from epoll
    epoll_ctl(epollfd_global, EPOLL_CTL_DEL, fd, nullptr);
    close(fd);
    clients.erase(it);
}

void start_next_question(Quiz &q); // forward declaration

void start_reveal_timer(Quiz &q, int secs = 5) {
    // ensure any previous timer cleaned up
    if (q.timerfd != -1) {
        epoll_ctl(epollfd_global, EPOLL_CTL_DEL, q.timerfd, nullptr);
        timerfd2quiz.erase(q.timerfd);
        close(q.timerfd);
        q.timerfd = -1;
    }
    int tfd = timerfd_create(CLOCK_MONOTONIC, TFD_NONBLOCK | TFD_CLOEXEC);
    if (tfd == -1) {
        // can't create timer -> skip reveal delay and immediately start next question
        q.phase = PHASE_QUESTION;
        q.current_q++;
        start_next_question(q);
        return;
    }
    struct itimerspec its;
    memset(&its, 0, sizeof(its));
    its.it_value.tv_sec = secs;
    its.it_value.tv_nsec = 0;
    if (timerfd_settime(tfd, 0, &its, nullptr) == -1) {
        close(tfd);
        q.phase = PHASE_QUESTION;
        q.current_q++;
        start_next_question(q);
        return;
    }
    q.timerfd = tfd;
    timerfd2quiz[tfd] = q.code;
    struct epoll_event ev;
    ev.events = EPOLLIN;
    ev.data.fd = tfd;
    if (epoll_ctl(epollfd_global, EPOLL_CTL_ADD, tfd, &ev) == -1) {
        // If epoll add fails, clean up timer and skip reveal delay
        timerfd2quiz.erase(tfd);
        close(tfd);
        q.timerfd = -1;
        // reveal phase ends here; transition back to question phase
        q.phase = PHASE_QUESTION;
        q.current_q++;
        start_next_question(q);
        return;
    }
}

void process_answer_for_question(Quiz &q) {
    // compute correct index
    if (q.current_q >= q.questions.size()) return;
    const Question &Q = q.questions[q.current_q];
    int correct = Q.correct_index;
    // award points to those whose responses match
    for (const auto &pr : q.responses) {
        const string &nick = pr.first;
        int ans = pr.second;
        if (ans == correct) {
            q.scores[nick] += Q.points;
        }
    }
    // Prepare SCORES message
    vector<pair<int,string>> v;
    transform(
        q.scores.begin(), q.scores.end(),
        back_inserter(v),
        [](const auto &pr){ return pair{-pr.second, pr.first}; }
    );
    sort(v.begin(), v.end());
    vector<string> s;
    transform(
        v.begin(), v.end(),
        back_inserter(s),
        [&](const auto &p) {
            return p.second + ":" + to_string(q.scores[p.second]);
        }
    );
    string scores_msg = "SCORES|" + join(s, ',');
    string reveal_msg = "REVEAL|" + to_string(correct);
    // Send to all participants and creator
    broadcast_to_quiz(q, reveal_msg, true, true);
    broadcast_to_quiz(q, scores_msg, true, true);
    // clear responses for next question
    q.responses.clear();

    // Enter reveal phase and start reveal timer (5 seconds)
    q.phase = PHASE_REVEAL;
    start_reveal_timer(q, 5);
}

void start_next_question(Quiz &q) {
    if (!q.started) return;
    if (q.current_q >= q.questions.size()) {
        // Compute and broadcast final scoreboard
        vector<pair<int,string>> v;
        transform(
            q.scores.begin(), q.scores.end(),
            back_inserter(v),
            [](const auto &pr){ return pair{-pr.second, pr.first}; }
        );
        sort(v.begin(), v.end());
        vector<string> s;
        transform(
            v.begin(), v.end(),
            back_inserter(s),
            [&](const auto &p) {
                return p.second + ":" + to_string(q.scores[p.second]);
            }
        );
        string final_msg = "FINAL_SCORES|" + join(s, ',');
        broadcast_to_quiz(q, final_msg, true, true);
        broadcast_to_quiz(q, "QUIZ_END", true, true);
        // Cleanup: stop timers, detach clients, and remove quiz
        if (q.timerfd != -1) {
            epoll_ctl(epollfd_global, EPOLL_CTL_DEL, q.timerfd, nullptr);
            timerfd2quiz.erase(q.timerfd);
            close(q.timerfd);
            q.timerfd = -1;
        }
        if (clients.count(q.creator_fd)) clients[q.creator_fd].quiz_code.clear();
        for (int pfd : q.players) {
            if (clients.count(pfd)) clients[pfd].quiz_code.clear();
        }
        quizzes.erase(q.code);
        return;
    }

    q.phase = PHASE_QUESTION;

    Question &Q = q.questions[q.current_q];
    // Determine participants_for_threshold as number of connected players currently in q.players
    int connected_players = 0;
    connected_players = count_if(
        q.players.begin(), q.players.end(),
        [&](int pfd){ return clients.count(pfd); }
    );
    q.participants_for_threshold = connected_players;

    // Send QUESTION to players
    string opts = join(vector<string>(Q.opts.begin(), Q.opts.end()), ';');
    string qmsg = "QUESTION|" + to_string((int)q.current_q) + "|" + Q.text + "|" + opts + "|" + to_string(Q.time_limit);
    string qview = "QUESTION_VIEW|" + to_string((int)q.current_q) + "|" + Q.text + "|" + opts + "|" + to_string(Q.time_limit);
    broadcast_to_quiz(q, qview, true, false);
    broadcast_to_quiz(q, qmsg, false, true);

    // Setup timerfd for this question (clean previous if any)
    if (q.timerfd != -1) {
        epoll_ctl(epollfd_global, EPOLL_CTL_DEL, q.timerfd, nullptr);
        timerfd2quiz.erase(q.timerfd);
        close(q.timerfd);
        q.timerfd = -1;
    }
    int tfd = timerfd_create(CLOCK_MONOTONIC, TFD_NONBLOCK | TFD_CLOEXEC);
    if (tfd == -1) {
        // fallback: process no timer (will rely on 2/3 only)
        q.timerfd = -1;
        return;
    }
    struct itimerspec its;
    memset(&its, 0, sizeof(its));
    its.it_value.tv_sec = Q.time_limit;
    its.it_value.tv_nsec = 0;
    if (timerfd_settime(tfd, 0, &its, nullptr) == -1) {
        close(tfd);
        q.timerfd = -1;
        return;
    }
    // register tfd in epoll and mapping
    q.timerfd = tfd;
    struct epoll_event ev;
    ev.events = EPOLLIN;
    ev.data.fd = tfd;
    if (epoll_ctl(epollfd_global, EPOLL_CTL_ADD, tfd, &ev) == -1) {
        // ignore
    } else {
        timerfd2quiz[tfd] = q.code;
    }
}

void handle_timer_event(int tfd) {
    // read timer to clear
    uint64_t expirations;
    read(tfd, &expirations, sizeof(expirations));
    auto it = timerfd2quiz.find(tfd);
    if (it == timerfd2quiz.end()) return;
    string code = it->second;
    auto qit = quizzes.find(code);
    if (qit == quizzes.end()) {
        timerfd2quiz.erase(it);
        return;
    }
    Quiz &q = qit->second;

    if (q.phase == PHASE_QUESTION) {
        // timer fired for the question -> stop and remove this timer, then process answers and start reveal timer
        if (q.timerfd == tfd) {
            epoll_ctl(epollfd_global, EPOLL_CTL_DEL, q.timerfd, nullptr);
            timerfd2quiz.erase(q.timerfd);
            close(q.timerfd);
            q.timerfd = -1;
        }
        // Process question end due to timeout => this will set phase = PHASE_REVEAL and start reveal timer
        process_answer_for_question(q);
    } else {
        // q.phase == PHASE_REVEAL: this timer fired for the reveal pause
        if (q.timerfd == tfd) {
            epoll_ctl(epollfd_global, EPOLL_CTL_DEL, q.timerfd, nullptr);
            timerfd2quiz.erase(q.timerfd);
            close(q.timerfd);
            q.timerfd = -1;
        }
        // after reveal pause -> go to next question
        q.phase = PHASE_QUESTION;
        q.current_q++;
        start_next_question(q);
    }
}

void try_process_threshold(Quiz &q) {
    if (q.participants_for_threshold == 0) {
        // no players -> end quiz
        q.current_q = q.questions.size();
        start_next_question(q);
        return;
    }
    int responses = (int)q.responses.size();
    int threshold = (int)ceil(2.0 * q.participants_for_threshold / 3.0);
    if (responses >= threshold) {
        // stop timer and process immediately
        if (q.timerfd != -1) {
            // delete timerfd from epoll and close
            epoll_ctl(epollfd_global, EPOLL_CTL_DEL, q.timerfd, nullptr);
            timerfd2quiz.erase(q.timerfd);
            close(q.timerfd);
            q.timerfd = -1;
        }
        // Process question answers and enter reveal phase (reveal timer will be started inside)
        process_answer_for_question(q);
        // do NOT advance q.current_q here — advance will occur after reveal timer expires
    } else {
        // Wait for more answers or timer expiration
    }
}

void handle_client_command(int fd, const string &line) {
    Client &c = clients[fd];
    string cmd = trim(line);
    if (cmd.empty()) return;
    // Parse by '|' parts
    if (cmd.rfind("ROLE ", 0) == 0) {
        // ROLE CREATOR nick OR ROLE PLAYER nick
        istringstream iss(cmd);
        string roleword, roletype, nick;
        iss >> roleword >> roletype >> nick;
        if (nick.empty()) {
            queue_send(c, string("ERR|Missing nick"));
            return;
        }
        if (nick2fd.count(nick)) {
            queue_send(c, "NICK_TAKEN");
            return;
        }
        c.nick = nick;
        nick2fd[nick] = fd;
        if (roletype == "CREATOR") c.role = ROLE_CREATOR;
        else c.role = ROLE_PLAYER;
        queue_send(c, "OK");
        return;
    }
    if (c.role == ROLE_NONE) {
        queue_send(c, "ERR|Set ROLE first with ROLE CREATOR/PLAYER <nick>");
        return;
    }
    if (c.role == ROLE_CREATOR) {
        // handle creator commands
        if (cmd.rfind("ADD_QUESTION|", 0) == 0) {
            // format: ADD_QUESTION|question|opt1;opt2;...|correct_index|points|time_sec
            vector<string> parts = split(cmd, '|');
            if (parts.size() < 6) {
                queue_send(c, "ERR|Invalid ADD_QUESTION format");
                return;
            }
            string qtext = parts[1];
            vector<string> opts = split(parts[2], ';');
            int correct = stoi(parts[3]);
            int points = stoi(parts[4]);
            int tsec = stoi(parts[5]);
            // The draft quiz is identified by a temporary key "_draft_<creator_fd>"
            string draft_code = string("_draft_") + to_string(fd);
            if (!quizzes.count(draft_code)) {
                Quiz q;
                q.code = draft_code;
                q.creator_fd = fd;
                quizzes[draft_code] = q;
            }
            Quiz &q = quizzes[draft_code];
            Question Q;
            Q.text = qtext;
            Q.opts = opts;
            Q.correct_index = correct;
            Q.points = points;
            Q.time_limit = tsec;
            q.questions.push_back(Q);
            queue_send(c, "QUESTION_ADDED");
            return;
        } else if (cmd == "SAVE_QUIZ") {
            string draft_code = string("_draft_") + to_string(fd);
            auto it = quizzes.find(draft_code);
            if (it == quizzes.end()) {
                queue_send(c, "ERR|No questions added");
                return;
            }
            Quiz q = it->second;
            quizzes.erase(it);
            // generate code and ensure uniqueness
            string code;
            do { code = gen_code(); } while (quizzes.count(code));
            q.code = code;
            q.creator_fd = fd;
            q.started = false;
            q.current_q = 0;
            q.timerfd = -1;
            quizzes[code] = q;
            // assign to client
            c.quiz_code = code;
            queue_send(c, string("QUIZ_CREATED|") + code);
            // send initial lobby update (creator only)
            send_lobby_update(quizzes[code]);
            return;
        } else if (cmd == "START") {
            if (c.quiz_code.empty()) {
                queue_send(c, "ERR|No quiz created/saved");
                return;
            }
            auto it = quizzes.find(c.quiz_code);
            if (it == quizzes.end()) {
                queue_send(c, "ERR|Quiz not found");
                c.quiz_code.clear();
                return;
            }
            Quiz &q = it->second;
            if (q.started) {
                queue_send(c, "ERR|Quiz already started");
                return;
            }
            if (q.players.empty()) {
                queue_send(c, "NOT_ENOUGH_PLAYERS");
                return;
            }
            q.started = true;
            // initialize scoreboard (ensure all players have entries)
            for (int pfd : q.players) {
                if (clients.count(pfd)) {
                    string pn = clients[pfd].nick;
                    if (!pn.empty() && !q.scores.count(pn)) q.scores[pn] = 0;
                }
            }
            // notify
            broadcast_to_quiz(q, "QUIZ_STARTED", true, true);
            // start first question
            start_next_question(q);
            return;
        } else {
            queue_send(c, "ERR|Unknown creator command");
            return;
        }
    } else if (c.role == ROLE_PLAYER) {
        // handle player commands
        if (cmd.rfind("JOIN|", 0) == 0) {
            string code = cmd.substr(5);
            code = trim(code);
            // find quiz by code
            auto it = quizzes.find(code);
            if (it == quizzes.end()) {
                queue_send(c, "NO_SUCH_QUIZ");
                return;
            }
            Quiz &q = it->second;
            if (q.started) {
                queue_send(c, "ALREADY_STARTED");
                return;
            }
            // add player fd to quiz.players
            q.players.insert(fd);
            c.quiz_code = code;
            // add to scoreboard with 0
            if (!c.nick.empty()) q.scores[c.nick] = 0;
            queue_send(c, "JOINED");
            // update lobby for all
            send_lobby_update(q);
            return;
        } else if (cmd.rfind("ANSWER|", 0) == 0) {
            if (c.quiz_code.empty()) {
                queue_send(c, "ERR|Not in a quiz");
                return;
            }
            auto it = quizzes.find(c.quiz_code);
            if (it == quizzes.end()) {
                queue_send(c, "ERR|Quiz not found");
                c.quiz_code.clear();
                return;
            }
            Quiz &q = it->second;
            if (!q.started) {
                queue_send(c, "ERR|Quiz not started");
                return;
            }
            if (q.current_q >= q.questions.size()) {
                queue_send(c, "ERR|No active question");
                return;
            }
            // parse answer safely
            int ans = 0;
            try {
                ans = stoi(cmd.substr(7));
            } catch (...) {
                queue_send(c, "ERR|Invalid answer");
                return;
            }
            // record response by nick
            string nick = c.nick;
            if (nick.empty()) {
                queue_send(c, "ERR|No nick");
                return;
            }
            if (q.phase != PHASE_QUESTION) {
                queue_send(c, "ERR|Not accepting answers now");
                return;
            }
            // Only first answer counts
            if (!q.responses.count(nick)) {
                q.responses[nick] = ans;
                // send ack
                queue_send(c, "ANSWER_RECEIVED");
                // notify creator about incoming response
                string creator_msg = string("PLAYER_ANSWERED|") + nick + "|" + to_string(ans);
                if (clients.count(q.creator_fd)) queue_send(clients[q.creator_fd], creator_msg);
                // check 2/3 threshold (only meaningful in question phase)
                if (q.phase == PHASE_QUESTION) try_process_threshold(q);
            } else {
                queue_send(c, "ERR|Already answered");
            }
            return;
        } else {
            queue_send(c, "ERR|Unknown player command");
            return;
        }
    }
}

int main(int argc, char* argv[]) {
    int port = 12345;
    if (argc >= 2) port = atoi(argv[1]);

    // create listening socket
    int sfd = socket(AF_INET, SOCK_STREAM, 0);
    if (sfd == -1) { perror("socket"); return 1; }

    int yes = 1;
    setsockopt(sfd, SOL_SOCKET, SO_REUSEADDR, &yes, sizeof(yes));

    struct sockaddr_in addr;
    memset(&addr,0,sizeof(addr));
    addr.sin_family = AF_INET;
    addr.sin_addr.s_addr = INADDR_ANY;
    addr.sin_port = htons(port);

    if (bind(sfd, reinterpret_cast<struct sockaddr*>(&addr), sizeof(addr)) == -1) { perror("bind"); close(sfd); return 1; }
    if (listen(sfd, SOMAXCONN) == -1) { perror("listen"); close(sfd); return 1; }
    make_socket_non_blocking(sfd);

    int efd = epoll_create1(0);
    if (efd == -1) { perror("epoll_create1"); close(sfd); return 1; }
    epollfd_global = efd;
    listenfd_global = sfd;

    struct epoll_event ev;
    ev.events = EPOLLIN;
    ev.data.fd = sfd;
    if (epoll_ctl(efd, EPOLL_CTL_ADD, sfd, &ev) == -1) { perror("epoll_ctl add listen"); close(sfd); close(efd); return 1; }

    cout << "Server started on port " << port << endl;

    struct epoll_event events[MAX_EVENTS];

    while (true) {
        int n = epoll_wait(efd, events, MAX_EVENTS, -1);
        if (n == -1) {
            if (errno == EINTR) continue;
            perror("epoll_wait");
            break;
        }
        for (int i=0;i<n;i++) {
            int fd = events[i].data.fd;
            uint32_t evts = events[i].events;
            if (fd == sfd) {
                // accept new
                while (true) {
                    struct sockaddr_in in_addr;
                    socklen_t in_len = sizeof(in_addr);
                    int infd = accept(sfd, reinterpret_cast<struct sockaddr*>(&in_addr), &in_len);
                    if (infd == -1) {
                        if (errno == EAGAIN || errno == EWOULDBLOCK) break;
                        else { perror("accept"); break; }
                    }
                    make_socket_non_blocking(infd);
                    struct epoll_event ev2;
                    ev2.events = EPOLLIN;
                    ev2.data.fd = infd;
                    if (epoll_ctl(efd, EPOLL_CTL_ADD, infd, &ev2) == -1) {
                        perror("epoll_ctl add client");
                        close(infd);
                        continue;
                    }
                    Client c;
                    c.fd = infd;
                    clients[infd] = c;
                    queue_send(clients[infd], "WELCOME|Send ROLE CREATOR/PLAYER <nick>");
                }
            } else {
                // check if fd is a timerfd
                if (timerfd2quiz.count(fd)) {
                    if (evts & EPOLLIN) {
                        handle_timer_event(fd);
                    }
                    continue;
                }
                // handle client events
                if (evts & EPOLLIN) {
                    // read data
                    bool closed_conn = false;
                    while (true) {
                        char buf[512];
                        ssize_t count = read(fd, buf, sizeof(buf));
                        if (count == -1) {
                            if (errno != EAGAIN) {
                                // error
                                closed_conn = true;
                            }
                            break;
                        } else if (count == 0) {
                            closed_conn = true;
                            break;
                        } else {
                            // append to inbuf
                            clients[fd].inbuf.append(buf, buf+count);
                            // extract lines
                            size_t pos;
                            while ((pos = clients[fd].inbuf.find('\n')) != string::npos) {
                                string line = clients[fd].inbuf.substr(0,pos);
                                clients[fd].inbuf.erase(0,pos+1);
                                handle_client_command(fd, line);
                            }
                            // limit buffer
                            if (clients[fd].inbuf.size() > BUFFER_LIMIT) {
                                queue_send(clients[fd], "ERR|Input too long, closing");
                                closed_conn = true;
                                break;
                            }
                        }
                    }
                    if (closed_conn) {
                        close_client(fd);
                        continue;
                    }
                }
                if (evts & EPOLLOUT) {
                    // send pending outbuf
                    Client &c = clients[fd];
                    while (!c.outbuf.empty()) {
                        string &s = c.outbuf.front();
                        ssize_t w = write(fd, s.c_str(), s.size());
                        if (w == -1) {
                            if (errno == EAGAIN || errno == EWOULDBLOCK) break;
                            // error -> close
                            close_client(fd);
                            break;
                        }
                        if ((size_t)w < s.size()) {
                            // partial write
                            s.erase(0, w);
                            break;
                        } else {
                            c.outbuf.pop_front();
                        }
                    }
                    if (clients.count(fd)) {
                        // if outbuf empty, disable EPOLLOUT
                        if (clients[fd].outbuf.empty()) modify_epoll_out(fd, false);
                    }
                }
                if (evts & (EPOLLHUP | EPOLLERR)) {
                    close_client(fd);
                }
            }
        }

        // Ensure timerfd->quiz mapping is up-to-date for all active quizzes
        timerfd2quiz.clear();
        for (const auto &pr : quizzes) {
            if (pr.second.timerfd != -1) timerfd2quiz[pr.second.timerfd] = pr.first;
        }
    }

    // cleanup
    close(sfd);
    close(efd);
    return 0;
}
