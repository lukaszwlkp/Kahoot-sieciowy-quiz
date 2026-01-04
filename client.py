#!/usr/bin/env python3
import socket
import sys
import threading
import tkinter as tk
from tkinter import ttk
from queue import Queue
from queue import Empty

#Queue for the server's messages
serverQueue=Queue(0)

#Default server's IP and PORT
host = "127.0.0.1"
port = 12345
CODE_LENGTH=6

#loop for receving data from  the server
def recvLoop(sock,stop_event):

    VALID_RESPONSES = {
        "OK","NICK_TAKEN","QUESTION_ADDED","QUIZ_CREATED","NO_SUCH_QUIZ",
        "ALREADY_STARTED","JOINED","LOBBY_PLAYERS","QUIZ_CANCELLED",
        "QUIZ_ABORTED","QUIZ_END","QUIZ_STARTED","REVEAL","SCORES",
        "QUESTION","QUESTION_VIEW","FINAL_SCORES","PLAYER_ANSWERED"
    }

    try:
        while not stop_event.is_set():
            try:
                data = sock.recv(4096)
            except Exception as e:
                serverQueue.put("[DISCONNECTED]")
                print("[DISCONNECTED]")
                break

            if not data:
                serverQueue.put("[DISCONNECTED]")
                print("[DISCONNECTED]")
                break

            text = data.decode(errors="ignore")
            for line in text.splitlines():
                print("[SERVER]", line)
                response = line.split("|", 1)[0]
                if response in VALID_RESPONSES:
                    serverQueue.put(line)
    finally:
        try:
            sock.shutdown(socket.SHUT_RDWR)
            sock.close()
        except Exception:
            pass


def send(sock, msg):
    try:
        print("[SEND]", msg)
        sock.sendall((msg + "\n").encode())
    except OSError:
        pass
        


def main():
    global host,port
    def cancelReapeatAndDestroy(window):
        window.eval('::ttk::CancelRepeat')
        window.destroy()
        return
    def closeAllAndExit(rootWindow=None):
        stopEvent.set()
        try:
            sock.shutdown(socket.SHUT_RDWR)
        except Exception:
            pass
        try:
            sock.close()
        except Exception:
            pass

        try:
            recvThread.join(timeout=2.0)
        except Exception:
            pass
        try:
            if rootWindow is not None:
                rootWindow.eval('::ttk::CancelRepeat')
                rootWindow.destroy()
        except Exception:
            pass
        sys.exit(0)

    #Window to set server's IP and PORT default values are 127.0.0.1 12345
    chooseServerIPAndPortWindow=tk.Tk(screenName=None, baseName="OnlineQuiz", className="OnlineQuiz", useTk=1)
    chooseServerIPAndPortWindow.protocol("WM_DELETE_WINDOW", sys.exit)
    chooseServerIPAndPortWindow.geometry("720x480")

    ipLabel=tk.Label(chooseServerIPAndPortWindow,text="Enter server's IP(IPv4):")
    ipLabel.grid(row=0,column=0)
    portLabel=tk.Label(chooseServerIPAndPortWindow,text="Chose server's port:")
    portLabel.grid(row=1,column=0)

    ip=tk.StringVar(value=str(host))
    ipEntry=tk.Entry(chooseServerIPAndPortWindow,textvariable=ip,width=20)
    ipEntry.grid(row=0,column=1)
    
    portNumber=tk.StringVar(value=str(port))
    portNumberSpinbox=tk.Spinbox(chooseServerIPAndPortWindow,from_=1024,to_=65535,state="normal",textvariable=portNumber)
    portNumberSpinbox.grid(row=1,column=1)
    
    def checkAndSetIPAndPort():
        global host,port
        if not portNumber.get().isnumeric():
            wrongDataLabel=tk.Label(
                chooseServerIPAndPortWindow,
                text="PORT MUST BE POSITIVE NUMBER\nFROM 1024 TO 65535",
                fg="red",
                font=("Arial", 16)

            )
            wrongDataLabel.grid(row=3,column=1)
            chooseServerIPAndPortWindow.after(3000,wrongDataLabel.destroy)
            return
        if int(portNumber.get())<1024 or int(portNumber.get())>65535:
            wrongDataLabel=tk.Label(
                chooseServerIPAndPortWindow,
                text="PORT MUST BE NUMBER \nFROM 1024 TO 65535",
                fg="red",
                font=("Arial", 16)

            )
            wrongDataLabel.grid(row=3,column=1)
            chooseServerIPAndPortWindow.after(2500,wrongDataLabel.destroy)
            return
        
        octets=ip.get().split(".")
        if len(octets)!=4:
            wrongDataLabel=tk.Label(
                chooseServerIPAndPortWindow,
                text="IP MUST BE IN\n X.X.X.X FORMAT",
                fg="red",
                font=("Arial", 16)

            )
            wrongDataLabel.grid(row=3,column=1)
            chooseServerIPAndPortWindow.after(2500,wrongDataLabel.destroy)
            return
        elif any((not octet.isnumeric()) for octet in octets):
            wrongDataLabel=tk.Label(
                chooseServerIPAndPortWindow,
                text="EVERY OCTET IN IP MUST BE INTEGER\n FROM 0 TO 255",
                fg="red",
                font=("Arial", 16)

            )
            wrongDataLabel.grid(row=3,column=1)
            chooseServerIPAndPortWindow.after(2500,wrongDataLabel.destroy)
            return
        elif any((int(octet)<0) for octet in octets) or any((int(octet)>255) for octet in octets):
            wrongDataLabel=tk.Label(
                chooseServerIPAndPortWindow,
                text="EVERY OCTET IN IP MUST BE INTEGER\n FROM 0 TO 255",
                fg="red",
                font=("Arial", 16)

            )
            wrongDataLabel.grid(row=3,column=1)
            chooseServerIPAndPortWindow.after(2500,wrongDataLabel.destroy)
            return
        
        host=ip.get()
        port=int(portNumber.get())

        CorrectDataLabel=tk.Label(
                chooseServerIPAndPortWindow,
                text="CORRECT IP AND PORT",
                fg="green",
                font=("Arial", 16)

            )
        confirmIPAndPortBtn.configure(state="disabled")
        CorrectDataLabel.grid(row=3,column=1)
        chooseServerIPAndPortWindow.after(2000,lambda:cancelReapeatAndDestroy(chooseServerIPAndPortWindow))


    confirmIPAndPortBtn=tk.Button(chooseServerIPAndPortWindow,text="CONFIRM",command=checkAndSetIPAndPort)        
    confirmIPAndPortBtn.grid(row=2,column=0)
    chooseServerIPAndPortWindow.mainloop()

    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.connect((host, port))
    except ConnectionRefusedError:
        infoWindow = tk.Tk(screenName=None, baseName="OnlineQuiz", className="OnlineQuiz", useTk=1)
        infoWindow.protocol("WM_DELETE_WINDOW", sys.exit)
        infoWindow.geometry("720x720")
        infoLabel = tk.Label(
                                infoWindow,
                                text="COULDN\'T CONNECT TO SERVER\nCHECK YOUR INTERNET CONNECTION",
                                fg="red",
                                font=("Arial", 16)
                            )
        infoLabel.pack()
        infoWindow.after(5000,sys.exit)
        infoWindow.mainloop()
    
    #start reader thread
    stopEvent = threading.Event()
    recvThread = threading.Thread(target=recvLoop, args=(sock, stopEvent), daemon=False)
    recvThread.start()
    
    #start window 

    startWindow = tk.Tk(screenName=None, baseName="OnlineQuiz", className="OnlineQuiz", useTk=1)
    startWindow.protocol("WM_DELETE_WINDOW", lambda: closeAllAndExit(startWindow))
    startWindow.geometry("720x720")
    playerName = tk.StringVar()
    playerRole=tk.StringVar()

    
    tk.Label(startWindow, text='User Name:').grid(row=0,column=0)
    userName=tk.Entry(startWindow,textvariable=playerName,width=40)
    userName.grid(row=0,column=1)
    
    tk.Label(startWindow, text='User Role:').grid(row=1,column=0)
    userRole = ttk.Combobox(startWindow, values=["CREATOR", "PLAYER"], state='readonly',textvariable=playerRole,width=40)
    userRole.set("PLAYER")
    userRole.grid(row=1,column=1)
    
  
    def chooseNameAndRole():
        prohibited=["host",";",",","\\n",".","you"," ","    "]
        for word in prohibited:
            if word in userName.get().lower():
                playerName.set("")
                userName.insert(0,f"Can't use \'{word}\' in the nickname")
                return
        if len(userName.get().strip())==0:
            playerName.set("")
            userName.insert(0,"NICK MUST BE AT LEAST ONE CHARACTER LONG")
            return
        line=None
        try:
            line = serverQueue.get_nowait()
        except Empty:
            line=None
        if line is not None:
            if line=="[DISCONNECTED]":
                for widget in startWindow.winfo_children():
                    widget.destroy()

                    info_label = tk.Label(
                        startWindow,
                        text="YOU ARE DISCONNECTED ",
                        fg="red"
                    )
                info_label.grid(row=0,column=0)
                startWindow.after(5000, lambda: closeAllAndExit(startWindow))
            return
        send(sock,f"ROLE {userRole.get()} {userName.get()}")
        try:
            response=serverQueue.get(block=True,timeout=5)
        except Empty:
            for widget in startWindow.winfo_children():
                widget.destroy()

                info_label = tk.Label(
                    startWindow,
                    text="NO RESPONSE FROM SERVER ",
                    fg="red"
                )
                info_label.grid(row=0,column=0)

            startWindow.after(5000, lambda: closeAllAndExit(startWindow))

        finally:
            if(response=="NICK_TAKEN"):
                userName.insert(0,"Someone's already used:")
            
            if(response=="OK"):
                for widget in startWindow.winfo_children():
                    widget.destroy()
                startWindow.destroy()

    confirmRoleAndName=tk.Button(startWindow,text="CONFIRM",command=chooseNameAndRole)
    confirmRoleAndName.grid(row=2,column=0)
    
    startWindow.mainloop()
    while True:
        if playerRole.get()=="CREATOR":#Creator window 

            creatorWindow=tk.Tk(screenName=None, baseName="OnlineQuiz", className="OnlineQuiz", useTk=1)
            creatorWindow.geometry("720x720")
            creatorWindow.protocol("WM_DELETE_WINDOW", lambda: closeAllAndExit(creatorWindow))
            numberOfQuestion=0
            quizCode=tk.StringVar()
            def addQuestion():
                numberOfAnswer=None

                addingQuestionWindow=tk.Toplevel(creatorWindow)
                addingQuestionWindow.protocol("WM_DELETE_WINDOW",addingQuestionWindow.destroy)
                addingQuestionWindow.title("Add question")
                addingQuestionWindow.geometry("720x720")
                answersNumber = tk.Spinbox(addingQuestionWindow, from_=2,to=10)
                answersNumber.grid(row=0,column=1)
                tk.Label(addingQuestionWindow,text='Number of answers(2-10):').grid(row=0,column=0)

                def creatingQuestion():
                    nonlocal numberOfAnswer
                    numberOfAnswer=answersNumber.get()
                    
                    if not numberOfAnswer.isnumeric():
                        wrongDataLabel=tk.Label(addingQuestionWindow,text="NUMBER OF ASNWERS MUST BE INTEGER BETWEEN 2 AND 10",fg="red")
                        wrongDataLabel.grid(row=1,column=1)
                        addingQuestionWindow.after(2000,wrongDataLabel.destroy)
                        return 
                    numberOfAnswer=int(numberOfAnswer)
                    if numberOfAnswer<2 or numberOfAnswer>10:
                        wrongDataLabel=tk.Label(addingQuestionWindow,text="NUMBER OF ASNWERS MUST BE INTEGER BETWEEN 2 AND 10",fg="red")
                        wrongDataLabel.grid(row=1,column=1)
                        addingQuestionWindow.after(2000,wrongDataLabel.destroy)
                        return
                    for widget in addingQuestionWindow.winfo_children():
                        widget.destroy()    
                    
                    QuestionContent=tk.StringVar(addingQuestionWindow,value="Type question")
                    AnswersContent=[tk.StringVar(addingQuestionWindow,value=f"Type answer") for i in range(numberOfAnswer)] 
                    tk.Label(addingQuestionWindow,text='Question:').grid(row=0,column=0)
                    Question=tk.Entry(addingQuestionWindow,textvariable=QuestionContent)
                    Question.grid(row=0,column=1)
                    for i in range(1,numberOfAnswer+1):
                        tk.Label(addingQuestionWindow,text=f"Answer number {i}:").grid(row=i,column=0)
                        tk.Entry(addingQuestionWindow,textvariable=AnswersContent[i-1]).grid(row=i,column=1)
                    

                    tk.Label(addingQuestionWindow,text='Correct answer:').grid(row=numberOfAnswer+1,column=0)
                    correctAnswer=tk.Spinbox(addingQuestionWindow, from_=1, to=numberOfAnswer)
                    correctAnswer.grid(row=numberOfAnswer+1,column=1)
                    
                    tk.Label(addingQuestionWindow,text='Points(at least 1 point):').grid(row=numberOfAnswer+2,column=0)
                    pointsForQuestion=tk.Spinbox(addingQuestionWindow, from_=1, to=float("inf"))
                    pointsForQuestion.grid(row=numberOfAnswer+2,column=1)

                    tk.Label(addingQuestionWindow,text='Time(at lest 10 seconds):').grid(row=numberOfAnswer+3,column=0)
                    timeAmount=tk.Spinbox(addingQuestionWindow, from_=10, to=float("inf"))
                    timeAmount.grid(row=numberOfAnswer+3,column=1)
                    
                    def savingQuestion():
                        nonlocal numberOfQuestion
                        points=pointsForQuestion.get()
                        time=timeAmount.get()
                        correct=correctAnswer.get()
                        if not points.isnumeric() or not time.isnumeric() or not correct.isnumeric():
                            wrongDataLabel=tk.Label(addingQuestionWindow,text="TIME,POINTS AND ID OF CORRECT ANSWER\n MUST BE POSITIVE INTEGERS",fg="red")
                            wrongDataLabel.grid(row=numberOfAnswer+5,column=0)
                            addingQuestionWindow.after(3250,wrongDataLabel.destroy)
                            return
                        points,time,correct=int(points),int(time),int(correct)
                        if points<1:
                            wrongDataLabel=tk.Label(addingQuestionWindow,text="AT LEAST 1 POINT FOR QUESTION",fg="red")
                            wrongDataLabel.grid(row=numberOfAnswer+5,column=0)
                            addingQuestionWindow.after(2500,wrongDataLabel.destroy)
                            return 
                        if time<10:
                            wrongDataLabel=tk.Label(addingQuestionWindow,text="AT LEAST 10 SECONDS FOR QUESTION",fg="red")
                            wrongDataLabel.grid(row=numberOfAnswer+5,column=0)
                            addingQuestionWindow.after(2500,wrongDataLabel.destroy)
                            return
                        if correct<1 or correct>numberOfAnswer:
                            wrongDataLabel=tk.Label(addingQuestionWindow,text=f"ID OF CORRECT ANSWER MUST BE \nFROM 1 TO {numberOfAnswer}",fg="red")
                            wrongDataLabel.grid(row=numberOfAnswer+5,column=0)
                            addingQuestionWindow.after(2500,wrongDataLabel.destroy)
                            return
                        line=None
                        try:
                            line = serverQueue.get_nowait()
                        except Empty:
                            line=None
                        if line is not None:
                            if line=="[DISCONNECTED]":
                                for widget in addingQuestionWindow.winfo_children():
                                    widget.destroy()

                                    info_label = tk.Label(
                                        addingQuestionWindow,
                                        text="YOU ARE DISCONNECTED ",
                                        fg="red"
                                    )
                                info_label.grid(row=0,column=0)
                                creatorWindow.after(5000, lambda: closeAllAndExit(creatorWindow))
                            return
                        msg=f"ADD_QUESTION|{Question.get()}|{";".join([answer.get() for answer in AnswersContent])}|{correct}|{points}|{time}"
                        send(sock,msg)
                        try:
                            response=serverQueue.get(block=True,timeout=5)
                        except Empty:
                            
                            for widget in addingQuestionWindow.winfo_children():
                                widget.destroy()

                                info_label = tk.Label(
                                    addingQuestionWindow,
                                    text="NO RESPONSE FROM SERVER\n COULDN\'T ADD THE QUESTION ",
                                    fg="red"
                                )
                            info_label.pack(padx=20, pady=20)

                            addingQuestionWindow.after(4000,addingQuestionWindow.destroy)
                        
                        finally:
                            for widget in addingQuestionWindow.winfo_children():
                                widget.destroy()

                            numberOfQuestion+=1
                            saveQuiz.configure(state="normal")
                            info_label = tk.Label(
                                addingQuestionWindow,
                                text="QUESTION ADDED",
                                fg="green"
                            )

                            info_label.pack(padx=20, pady=20)

                            addingQuestionWindow.after(1750, addingQuestionWindow.destroy)

                    saveQuestion=tk.Button(addingQuestionWindow,text="CONFIRM",command=savingQuestion)
                    saveQuestion.grid(row=numberOfAnswer+4,column=0)
                
                confirmNumbOfANswers=tk.Button(addingQuestionWindow,text="CONFIRM",command=creatingQuestion)
                confirmNumbOfANswers.grid(row=1,column=0)  
                
            def savingQuiz():
                nonlocal quizCode
                line=None
                try:
                    line = serverQueue.get_nowait()
                except Empty:
                    line=None
                if line is not None:
                    if line=="[DISCONNECTED]":
                        for widget in creatorWindow.winfo_children():
                            widget.destroy()

                            info_label = tk.Label(
                                creatorWindow,
                                text="YOU ARE DISCONNECTED ",
                                fg="red"
                            )
                        info_label.grid(row=0,column=0)
                        creatorWindow.after(5000, lambda: closeAllAndExit(creatorWindow))
                    return
                send(sock, "SAVE_QUIZ")
                try:
                    response = serverQueue.get(block=True, timeout=10)
                except Empty:
                    info_label = tk.Label(
                        creatorWindow,
                        text="COULDN'T CREATE QUIZ\n NO RESPONSE FROM SERVER",
                        fg="red",
                        font=("Arial", 16)
                    )
                    info_label.grid(row=2,column=2)
                    creatorWindow.after(3000,info_label.destroy)
                    return   
                if "QUIZ_CREATED" in response:
                    quizCode.set(response.split("|")[1])
                    for widget in creatorWindow.winfo_children():
                        widget.destroy()

                    info_label = tk.Label(
                        creatorWindow,
                        text="QUIZ CREATED",
                        fg="green",
                        font=("Arial", 16)
                    )
                

                info_label.pack(padx=20, pady=20)
                creatorWindow.after(1250,lambda:cancelReapeatAndDestroy(creatorWindow))
                

            addQuestions=tk.Button(creatorWindow,text="ADD QUESTIONS",command=addQuestion)
            addQuestions.grid(column=0,row=0) 
            saveQuiz=tk.Button(creatorWindow,text="SAVE QUIZ",state="disabled",command=savingQuiz)
            saveQuiz.grid(row=0,column=2)
            creatorWindow.mainloop()
        
        else:#PLAYER WINDOW 
            playerWindow=tk.Tk(screenName=None, baseName="OnlineQuiz", className="OnlineQuiz", useTk=1)
            playerWindow.geometry("720x720")
            playerWindow.protocol("WM_DELETE_WINDOW", lambda: closeAllAndExit(playerWindow))
            quizCode=tk.StringVar()
            quizCode.set("Enter game code")

            def joinGame():
                
                msg=f"JOIN|{quizCode.get()}"
                msg=msg.upper()
                if len(msg)!=(CODE_LENGTH+5) or not(all(char.isalnum() for char in quizCode.get())):
                    infoLabel = tk.Label(
                        playerWindow,
                        text=f"WRONG CODE FORMAT\n CODE MUST BE MADE FROM [A-Z0-9] \nAND {CODE_LENGTH} CHARACTERS LONG\n",
                        fg="red",
                        font=("Arial", 16)
                    )
                    infoLabel.pack()
                    playerWindow.after(2500,infoLabel.destroy)
                    return
                line=None
                try:
                    line = serverQueue.get_nowait()
                except Empty:
                    line=None
                if line is not None:
                    if line=="[DISCONNECTED]":
                        for widget in playerWindow.winfo_children():
                            widget.destroy()

                            info_label = tk.Label(
                                playerWindow,
                                text="YOU ARE DISCONNECTED ",
                                fg="red"
                            )
                        info_label.grid(row=0,column=0)
                        playerWindow.after(5000, lambda: closeAllAndExit(playerWindow))
                    return
                send(sock,msg)
                try:
                    response = serverQueue.get(block=True, timeout=10)
                except Empty:
                    quizCode.set("NO RESPONSE FROMS ERVER")
                    return   
                
                if "ALREADY_STARTED" in response:
                    infoLabel = tk.Label(
                        playerWindow,
                        text="COULDN'T JOIN\nQUIZ ALREADY STARTED ",
                        fg="red",
                        font=("Arial", 16)
                    )
                    infoLabel.pack()
                    playerWindow.after(1750,infoLabel.destroy)
                elif "NO_SUCH_QUIZ" in response:
                    infoLabel = tk.Label(
                        playerWindow,
                        text="COULDN'T JOIN\nNO SUCH QUIZ",
                        fg="red",
                        font=("Arial", 16)
                    )
                    infoLabel.pack()
                    playerWindow.after(1750,infoLabel.destroy)
                elif "JOINED" in response:
                    for widget in playerWindow.winfo_children():
                        widget.destroy()
                    infoLabel = tk.Label(
                        playerWindow,
                        text="JOINED QUIZ",
                        fg="green",
                        font=("Arial", 16)
                    )
                    infoLabel.pack()
                    playerWindow.after(850,lambda:cancelReapeatAndDestroy(playerWindow))


            tk.Label(playerWindow,text="Quiz code:").pack()
            enterCode=tk.Entry(playerWindow,textvariable=quizCode)
            enterCode.pack()
            joinGameBtn=tk.Button(playerWindow,text="JOIN GAME",command=joinGame)
            joinGameBtn.pack()
            playerWindow.mainloop()

    #LOBBY WINDOW
        lobbyWindow = tk.Tk(screenName=None, baseName="OnlineQuiz", className="OnlineQuiz", useTk=1)
        lobbyWindow.geometry("720x720")
        lobbyWindow.protocol("WM_DELETE_WINDOW", lambda: closeAllAndExit(lobbyWindow))

        code = tk.Label(lobbyWindow, text=f"Game Code: {quizCode.get().upper()}")
        code.pack()

        startGameBtn = None

        def startGame():
            send(sock, "START")

        if playerRole.get() == "CREATOR":
            startGameBtn = tk.Button(lobbyWindow, text="START", state="disabled", command=startGame)
            startGameBtn.pack()

        userScrollbar = tk.Scrollbar(lobbyWindow)
        userScrollbar.pack(side=tk.RIGHT, fill=tk.Y, padx=(0,4))

        userList = tk.Listbox(lobbyWindow, yscrollcommand=userScrollbar.set)
        userList.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(4,0), pady=8)
        userScrollbar.config(command=userList.yview)

        def startGameWindow():
            nonlocal playerRole
            global gameWindow
            gameWindow = tk.Tk()
            gameWindow.title("OnlineQuiz - Game")
            gameWindow.geometry("720x720")
            gameWindow.protocol("WM_DELETE_WINDOW", lambda: closeAllAndExit(gameWindow))

            
            finalResults = []
            quizEnded = False
            seeFullRankingBtn = None
            timerRunning = True
            answersListbox = None
            actualResultsListbox=None
            answersBuffer = []
            actualResults=[]

            question_label = tk.Label(gameWindow, text="Waiting for question...", wraplength=440, font=("Arial", 14))
            question_label.pack(pady=10)

            answersFrame = tk.Frame(gameWindow)
            answersFrame.pack(fill=tk.BOTH, padx=8)

            timerLabel = tk.Label(gameWindow, text="Time: -")
            timerLabel.pack(pady=6)


            answersButtons = []
            countdownJob = [None]



            def openAnswersWindow():
                nonlocal answersListbox,answersBuffer

                answersWindow = tk.Toplevel(gameWindow)
                answersWindow.title("Live answers")
                answersWindow.geometry("360x420")

                asnwersScrollbar = tk.Scrollbar(answersWindow)
                asnwersScrollbar.pack(side=tk.RIGHT, fill=tk.Y)

                answersListbox = tk.Listbox(answersWindow, yscrollcommand=asnwersScrollbar.set)
                answersListbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

                asnwersScrollbar.config(command=answersListbox.yview)


                for entry in answersBuffer:
                    answersListbox.insert(tk.END, entry)

                def onClose():
                    nonlocal answersListbox
                    answersListbox = None
                    answersWindow.destroy()

                answersWindow.protocol("WM_DELETE_WINDOW", onClose)
            


            if playerRole.get() == "CREATOR":
                showAnswersBtn = tk.Button(
                    gameWindow,
                    text="SHOW ACTUAL ANSWERS",
                    command=openAnswersWindow
                )
                showAnswersBtn.pack(pady=(0,6))
                    
            def clearAnswers():
                nonlocal answersButtons
                for btn in answersButtons:
                    btn.destroy()
                answersButtons = []

            def startTimer(seconds):
                sec = int(seconds)
                timerLabel.config(text=f"Time: {sec}s")
                if countdownJob[0]:
                    gameWindow.after_cancel(countdownJob[0])
                    
                def tick():
                    nonlocal sec,timerRunning
                    if not timerRunning:
                        return
                    
                    sec -= 1
                    timerLabel.config(text=f"Time: {max(sec,0)}s")
                    if sec <= 0:
                        countdownJob[0] = None
                        for btn in answersButtons:
                            btn.configure(state="disabled")
                        return
                    countdownJob[0]=gameWindow.after(1000, tick)

                countdownJob[0]=gameWindow.after(1000, tick)

            def sendAnswer(idx):
                try:
                    send(sock, f"ANSWER|{idx}")
                except Exception as e:
                    print("Error during sending:", e)

                if countdownJob[0]:
                    gameWindow.after_cancel(countdownJob[0])
                    countdownJob[0] = None
            

                timerLabel.config(text="Answered")
                for answerBtn in answersButtons:
                    answerBtn.configure(state="disabled")
                    

            def showQuestion(parts):
                clearAnswers()
                nonlocal answersListbox,answersBuffer
                
                answersBuffer.clear()

                if answersListbox is not None:
                    answersListbox.delete(0, tk.END)

                qtext = parts[2]
                opts = parts[3].split(";")
                time_limit = int(parts[4])
                
                question_label.config(text=qtext)
                for i, opt in enumerate(opts):
                    if playerRole.get() == "CREATOR":
                        state = tk.DISABLED
                    else:
                        state=tk.NORMAL
                    answerBtn = tk.Button(answersFrame, text=f"{i+1}. {opt}", anchor="w", wraplength=420,
                                    state=state, command=lambda i=i: sendAnswer(i+1))
                    answerBtn.pack(fill=tk.X, pady=3)
                    answersButtons.append(answerBtn)
                startTimer(time_limit)

            def handleReveal(payload):
                correct = int(payload)-1
                if countdownJob[0]:
                    gameWindow.after_cancel(countdownJob[0])
                    countdownJob[0] = None
                timerLabel.config(text="Revealed")
                for i, b in enumerate(answersButtons):
                    b.configure(bg=("green" if i == correct else "red"))
            
            def showActualRanking():
                nonlocal playerName,actualResults,actualResultsListbox
                
                actualResultsWindow=tk.Toplevel(gameWindow)
                actualResultsWindow.title("Actual scores")
                actualResultsWindow.geometry("480x360")

                title = tk.Label(actualResultsWindow,text="ACTUAL RANKING", font=("Arial", 16, "bold"))
                title.pack(pady=(8, 6))


                actualResultsScrollbar=tk.Scrollbar(actualResultsWindow)
                actualResultsScrollbar.pack(side=tk.RIGHT,fill=tk.Y,expand=True,padx=(0,1))

                actualResultsListbox=tk.Listbox(actualResultsWindow,yscrollcommand=actualResultsScrollbar.set)
                actualResultsListbox.pack(side=tk.LEFT,expand=True,fill=tk.BOTH,padx=(4,0), pady=8)
                actualResultsScrollbar.config(command=actualResultsListbox.yview)      
                
                results=[p.strip() for p in actualResults]
                for result in results:
                    name,score=result.split(":")
                    if name ==playerName.get():
                        actualResultsListbox.insert(tk.END,f"(YOU){name}:{score}")
                    else:
                        actualResultsListbox.insert(tk.END,result)

                def onClose():
                    nonlocal actualResultsListbox,actualResultsWindow
                    actualResultsListbox=None
                    actualResultsWindow.destroy()

                actualResultsWindow.protocol("WM_DELETE_WINDOW",onClose)
                closeBtn = tk.Button(actualResultsWindow, text="CLOSE", command=onClose)
                closeBtn.pack(pady=10)

            scoresBtn = tk.Button(gameWindow, text="ACTUAL RANKING",command=showActualRanking)
            scoresBtn.pack(pady=6)

            def showFinalRanking():
                nonlocal finalResults,playerName

                finalWindow = tk.Toplevel(gameWindow)
                finalWindow.title("FINAL RANKING")
                finalWindow.geometry("480x360")

                title = tk.Label(finalWindow, text="FINAL RANKING", font=("Arial", 16, "bold"))
                title.pack(pady=(8, 6))

                
                finalScoresScrollbar = tk.Scrollbar(finalWindow)
                finalScoresScrollbar.pack(side=tk.RIGHT, fill=tk.Y, pady=8)

                FinalList = tk.Listbox(finalWindow, yscrollcommand=finalScoresScrollbar.set)
                FinalList.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(4,0), pady=8)
                finalScoresScrollbar.config(command=FinalList.yview)
                
                pairs = [p.strip() for p in str(finalResults).split(",") if p.strip()]
                for p in pairs:
                    name,score=p.split(":")
                    if name == playerName.get():
                        FinalList.insert(tk.END, f"(YOU){name}:{score}")
                    else:
                        FinalList.insert(tk.END, p)

                closeBtn = tk.Button(finalWindow, text="CLOSE", command=finalWindow.destroy)
                closeBtn.pack(pady=10)


            def processServerMessagesGame():
                nonlocal finalResults, quizEnded, seeFullRankingBtn,timerRunning,actualResults,actualResultsListbox,answersListbox,answersBuffer
                if quizEnded:
                    return
                try:
                    while True:
                        try:
                            line = serverQueue.get_nowait()
                        except Empty:
                            break

                        if line.startswith("QUESTION|") or line.startswith("QUESTION_VIEW|"):
                            parts = line.split("|")
                            showQuestion(parts)
                        elif line == "[DISCONNECTED]":
                            timerRunning = False
                            quizEnded = True
                            if countdownJob[0]:
                                gameWindow.after_cancel(countdownJob[0])
                                countdownJob[0] = None
                            for widget in gameWindow.winfo_children():
                                widget.destroy()

                            infoLabel = tk.Label(
                                gameWindow,
                                text="YOU ARE DISCONNECTED",
                                fg="red",
                                font=("Arial", 16)
                            )
                            try:
                                infoLabel.pack()
                            except:
                                pass
                            gameWindow.after(5000, lambda: closeAllAndExit(gameWindow))
                            
                            return
                        elif line.startswith("REVEAL"):
                            _, payload = line.split("|") 
                            handleReveal(payload)
                        elif line.startswith("SCORES"):
                            _, payload = line.split("|")
                            actualResults=payload.split(",")
                            if actualResultsListbox is not None:
                                actualResultsListbox.delete(0,tk.END)
                                results=[p.strip() for p in actualResults]
                                for result in results:
                                    name,score=result.split(":")
                                    if name ==playerName.get():
                                        actualResultsListbox.insert(tk.END,f"(YOU){name}:{score}")
                                    else:
                                        actualResultsListbox.insert(tk.END,result)

                        elif line.startswith("PLAYER_ANSWERED|"):
                            parts = line.split("|", 2)
                            _, nick, answer = parts
                            entry = f"{nick}: {answer}"
                            answersBuffer.append(entry)
                            if answersListbox is not None:
                                answersListbox.insert(tk.END, entry)

                        elif line.startswith("FINAL_SCORES"):
                            _, payload = line.split("|")
                            finalResults = payload

                            if quizEnded and seeFullRankingBtn is not None:
                                seeFullRankingBtn.configure(state=tk.NORMAL, text="SEE FULL RANKING")
                                
                        elif line.startswith("QUIZ_ABORTED"):
                            timerRunning = False
                            quizEnded = True
                            if countdownJob[0]:
                                gameWindow.after_cancel(countdownJob[0])
                                countdownJob[0] = None

                            for widget in gameWindow.winfo_children():   
                                widget.destroy()
                                
                            quizAborted=tk.Label(gameWindow, text="QUIZ HAS BEEN ABORTED", fg="red", font=("Arial", 16))
                            quizAborted.pack()
                            gameWindow.after(5000,lambda: closeAllAndExit(gameWindow))

                        elif line.startswith("QUIZ_END"):
                            quizEnded = True
                            timerRunning = False
                            
                            if countdownJob[0]:
                                gameWindow.after_cancel(countdownJob[0])
                                countdownJob[0] = None

                            for widget in gameWindow.winfo_children():
                                widget.destroy()
                            

                            title = tk.Label(gameWindow, text="THE QUIZ HAS ENDED", font=("Arial", 16))
                            title.pack(pady=10)

                            if finalResults:
                                btn_text = "SEE FULL RANKING"
                                btn_state = tk.NORMAL
                            else:
                                btn_state=tk.DISABLED
                                btn_text="SEE FULL RANKING (waiting...)"
                            

                            seeFullRankingBtn = tk.Button(
                                gameWindow,
                                text=btn_text,
                                state=btn_state,
                                command=showFinalRanking
                            )
                            seeFullRankingBtn.pack(pady=10)
                            if playerRole.get()=="CREATOR":
                                text="CREATE NEW QUIZ"
                            elif playerRole.get()=="PLAYER":
                                text="JOIN NEW QUIZ"
                            goToLobbyBtn=tk.Button(gameWindow, text=text, command=lambda:cancelReapeatAndDestroy(gameWindow))
                            goToLobbyBtn.pack(pady=6)
                            closeBtn = tk.Button(gameWindow, text="CLOSE", command=lambda: closeAllAndExit(gameWindow))
                            closeBtn.pack(pady=6)

                        else:
                            pass
                except Exception as e:
                    print("Error (game):", e)

                gameWindow.after(50, processServerMessagesGame)

            gameWindow.after(100, processServerMessagesGame)
            gameWindow.mainloop()

        def startGameSequence():
            cancelReapeatAndDestroy(lobbyWindow)
            startGameWindow()

        def processServerMessagesLobby():
            try:
                while True:
                    try:
                        line = serverQueue.get_nowait()
                    except Empty:
                        break

                    parts = line.split("|", 1)
                    if len(parts) == 2:
                        cmd, payload = parts[0], parts[1]
                        if cmd == "LOBBY_PLAYERS":
                            players = [p.strip() for p in payload.split(",") if p.strip()]
                            userList.delete(0, tk.END)
                            for p in players:
                                if p == playerName.get() or p == f"{playerName.get()}(host)":
                                    userList.insert(tk.END, f"{p}(YOU)")
                                else:
                                    userList.insert(tk.END, p)

                            if len(players) > 1 and playerRole.get() == "CREATOR" and startGameBtn is not None:
                                startGameBtn.configure(state="normal")
                            continue 

                    if line == "QUIZ_STARTED":

                        lobbyWindow.after(0, startGameSequence)
                        return
                    elif line == "[DISCONNECTED]":
                            for widget in lobbyWindow.winfo_children():
                                widget.destroy()

                            infoLabel = tk.Label(
                                lobbyWindow,
                                text="YOU ARE DISCONNECTED",
                                fg="red",
                                font=("Arial", 16)
                            )
                            try:
                                infoLabel.pack()
                            except:
                                pass
                            
                            lobbyWindow.after(5000, lambda: closeAllAndExit(lobbyWindow))
                            return
                    elif line == "QUIZ_CANCELLED":
                        for widget in lobbyWindow.winfo_children():
                            widget.destroy()

                        info_label = tk.Label(
                            lobbyWindow,
                            text="QUIZ HAS BEEN CANCELED", 
                            fg="red",
                            font=("Arial", 16)
                            )
                        info_label.pack()

                        lobbyWindow.after(3000, lobbyWindow.after(3000, lambda:closeAllAndExit(lobbyWindow)))
                        return
                    else:
                        continue
            except Exception as e:
                print("Error (lobby):", e)

            lobbyWindow.after(50, processServerMessagesLobby)

        lobbyWindow.after(100, processServerMessagesLobby)
        lobbyWindow.mainloop()

if __name__ == "__main__":
    main()
