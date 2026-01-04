CXX = g++
CXXFLAGS = -std=c++17 -Wall -Wextra
DEBUGFLAGS = -std=c++17 -Wall -Wextra -g

TARGET = server
SRC = server.cpp
PYCLIENT = client.py

all: server

server: $(SRC)
	$(CXX) $(CXXFLAGS) -o $(TARGET) $(SRC)

debug: $(SRC)
	$(CXX) $(DEBUGFLAGS) -o $(TARGET) $(SRC)

run-server: server
	./$(TARGET)

run-client: server
	python3 $(PYCLIENT)

lint:
	cppcheck --enable=all --inconclusive --std=c++17 --force --suppress=missingIncludeSystem --quiet $(SRC)

valgrind: server
	valgrind --leak-check=full --show-leak-kinds=all --track-origins=yes ./$(TARGET)

clean:
	rm -f $(TARGET)
