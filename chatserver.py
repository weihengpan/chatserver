from asyncore import dispatcher
from asynchat import async_chat
import sys, socket, asyncore, datetime, random

NAME = 'PChat'
VER = '1.1.5'

help = [r'**Client Commands**',\
        r'/login <name>    *Login using the name*',\
        r'/logout          *Logout*',\
        r'/who             *See who is logged in*',\
        r'/help            *Get the help*']


def getPort():
    'Ask user the port number'
    if len(sys.argv) == 1:
        tp = raw_input('Port("r" for random):')
        if tp.lower() == 'r':
            p = random.randrange(49152,65535) # Get a random port from the floating ports list
            return p
        elif tp.isdigit() == True and 0 < int(tp) <= 65535: # Check if tp is a valid port number
            p = int(tp) # Return the value in int format
            return p
        else:
            print('Invalid value.')
            p = getPort() # Recursion
            return p
    elif sys.argv[1] == '-p':
        if sys.argv[2].isdigit() and (0 < int(sys.argv[2]) <= 65535) == True:
            p = int(sys.argv[2])
            return p
        elif sys.argv[2].lower() == 'r':
            p = random.randrange(49152,65535)
            return p
    else:
        print('Wrong arguments. Please try again.')
        sys.exit()

# Init!
port = getPort()
print('\r\n')
print('Port:', port)
print('Protocol: Telnet')
print('Server init...')

# Class definitions

class EndSession(Exception): pass

class CommandHandler:
    """
    Simple command handler similar to cmd.Cmd from the standard
    library.
    """

    def say(self, session, line):
        'Respond to a say command'
        self.broadcast(session.name+': '+line+'\r\n')

    def handle(self, session, line):
        'Handle a received line from a given session'
        text = line
        if not line.strip(): return
        # Split off the command:
        parts = line.split(' ', 1)
        cmd = parts[0]
        try: line = parts[1].strip()
        except IndexError: line = ''
        # Try to find a handler:
        try:
            if cmd[0] == r'/':
                meth = getattr(self, 'do_'+cmd[1:len(cmd)], None)
            else: 
                raise TypeError
            # Assume it's callable:
            meth(session, line)
        except TypeError:
            # If it isn't, respond to the say command:
            if session.name != None: 
                self.say(session, text)
            else:
                session.push('Please login first.\r\nThe login command is "/login <name>".\r\n')

class Room(CommandHandler):
    """
    A generic environment that may contain one or more users
    (sessions). It takes care of basic command handling and
    broadcasting.
    """

    def __init__(self, server):
        self.server = server
        self.sessions = []

    def add(self, session):
        'A session (user) has entered the room'
        self.sessions.append(session)

    def remove(self, session):
        'A session (user) has left the room'
        self.sessions.remove(session)

    def broadcast(self, line):
        'Send a line to all sessions in the room'
        for session in self.sessions:
            session.push(line)


    def do_logout(self, session, line):
        'Respond to the logout command'
        raise EndSession

class LoginRoom(Room):
    """
    A room meant for a single person who has just connected.
    """

    def add(self, session):
        Room.add(self, session)
        rawdate = datetime.datetime.now()
        date = str(rawdate.hour) + ':' + str(rawdate.minute) + ':' + str(rawdate.second) + ', ' + str(rawdate.year) + '.' + str(rawdate.month) + '.' + str(rawdate.day) + ' UTC+0800'
        # When a user enters, greet him/her:
        self.broadcast('Welcome to %s.\r\n' % self.server.name)
        self.broadcast('Time: %s\r\n' % date)
        self.broadcast('Ver. %s\r\n' % VER)

    def unknown(self, session, cmd):
        # All unknown commands (anything except login or logout)
        # results in a prodding:
        session.push('Please log in.\nUse "login <name>"\r\n')

    def do_login(self, session, line):
        name = line.strip()
        # Make sure the user has entered a name:
        if not name:
            session.push('Please enter a name.\r\n')
        # Make sure that the name isn't in use:
        elif name in self.server.users:
            session.push('The name "%s" is taken.\r\n' % name)
            session.push('Please try again.\r\n')
        else:
            # The name is OK, so it is stored in the session, and
            # the user is moved into the main room.
            session.name = name
            session.enter(self.server.main_room)
            hour = datetime.datetime.now().hour
            if 6 <= hour < 12:
                session.push('Good morning, %s, remember to concentrate your time to important things.' % name)
            elif 12 <= hour < 15:
                session.push("It's noon now, %s, how about take a nap?" % name)
            elif 15 <= hour < 18:
                session.push('Good afternoon, %s, what about a cup of tea?' % name)
            elif 18 <= hour < 22:
                session.push("Good evening, %s, time to watch TV with your family, ain't it?" % name)
            else:
                session.push("Time to sleep now, tired and hard-working %s, not like me." % name)
            session.push('\r\nWelcome home.\r\n')

class ChatRoom(Room):
    """
    A room meant for multiple users who can chat with the others in
    the room.
    """

    def add(self, session):
        # Notify everyone that a new user has entered:
        self.broadcast(session.name + ' has entered the room.\r\n')
        print(session.name + ' has entered the room.')
        self.server.users[session.name] = session
        Room.add(self, session)


    def remove(self, session):
        Room.remove(self, session)
        # Notify everyone that a user has left:
        self.broadcast(session.name + ' has left the room.\r\n')
        print(session.name + ' has left the room.')

    def do_look(self, session, line):
        'Handles the look command, used to see who is in a room'
        session.push('The following are in this room:\r\n')
        for other in self.sessions:
            session.push(other.name + '\r\n')

    def do_who(self, session, line):
        'Handles the who command, used to see who is logged in'
        session.push('The following are logged in:\r\n')
        for name in self.server.users:
            session.push(name + '\r\n')

    def do_help(self, session, line):
        "Handles the help command, used to show this server's help"
        session.push('\r\n')
        for h in help:
            session.push(h + '\r\n')

class LogoutRoom(Room):
    """
    A simple room for a single user. Its sole purpose is to remove
    the user's name from the server.
    """

    def add(self, session):
        # When a session (user) enters the LogoutRoom it is deleted
        try: del self.server.users[session.name]
        except KeyError: pass

class ChatSession(async_chat):
    """
    A single session, which takes care of the communication with a
    single user.
    """

    def __init__(self, server, sock):
        async_chat.__init__(self, sock)
        self.server = server
        self.set_terminator("\r\n")
        self.data = []
        self.name = None
        # All sessions begin in a separate LoginRoom:
        self.enter(LoginRoom(server))


    def enter(self, room):
        # Remove self from current room and add self to
        # next room...
        try: cur = self.room
        except AttributeError: pass
        else: cur.remove(self)
        self.room = room
        room.add(self)

    def collect_incoming_data(self, data):
        self.data.append(data)

    def found_terminator(self):
        line = ''.join(self.data)
        self.data = []
        try: self.room.handle(self, line)
        except EndSession:
            self.handle_close()

    def handle_close(self):
        async_chat.handle_close(self)
        self.enter(LogoutRoom(self.server))

class ChatServer(dispatcher):
    """
    A chat server with a single room.
    """

    def __init__(self, port, name):
        dispatcher.__init__(self)
        self.create_socket(socket.AF_INET, socket.SOCK_STREAM)
        self.set_reuse_addr()
        self.bind(('', port))
        self.listen(5)
        self.name = name
        self.users = {}
        self.main_room = ChatRoom(self)

    def handle_accept(self):
        conn, addr = self.accept()
        ChatSession(self, conn)

print('Server online.')

if __name__ == '__main__':
    s = ChatServer(port, NAME)
    try: asyncore.loop()
    except KeyboardInterrupt: print
