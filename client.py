import socket
import threading
import json
import curses
import sys
import traceback
from datetime import datetime

class ChatClient:
    def __init__(self, host='localhost', port=9999):
        self.host = host
        self.port = port
        self.client_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.username = None
        self.current_room = "general"
        self.running = False
        self.stdscr = None
        self.input_win = None
        self.chat_win = None
        self.status_win = None
        self.users_win = None
        self.messages = []
        self.input_text = ""
        self.cursor_pos = 0
        self.users_in_room = []
        self.is_admin = False  
    def connect(self, username):
        try:
            self.client_socket.connect((self.host, self.port))
            self.username = username
            # Enviar nome de usuário para o servidor
            self.client_socket.send(json.dumps({"username": username}).encode('utf-8'))
            return True
        except Exception as e:
            print(f"Erro de conexão: {e}")
            return False

    def start_ui(self):
        try:
            # Inicializar curses
            self.stdscr = curses.initscr()
            curses.noecho()
            curses.cbreak()
            self.stdscr.keypad(True)
            curses.start_color()
            curses.use_default_colors()
            curses.curs_set(1)  
            
            try:
                # Definir pares de cores
                curses.init_pair(1, curses.COLOR_GREEN, -1)     # Para nome de usuário
                curses.init_pair(2, curses.COLOR_CYAN, -1)      # Para sussuros
                curses.init_pair(3, curses.COLOR_YELLOW, -1)    # Para mensagens do sistema
                curses.init_pair(4, curses.COLOR_WHITE, -1)     # Para texto normal
                curses.init_pair(5, curses.COLOR_MAGENTA, -1)   # Para lista de usuários
                curses.init_pair(6, curses.COLOR_BLUE, -1)      # Para bordas
                curses.init_pair(7, curses.COLOR_RED, -1)       # Para erros
                curses.init_pair(8, curses.COLOR_BLACK, curses.COLOR_WHITE)  # Para barra de status
                
                
                max_y, max_x = self.stdscr.getmaxyx()
                
                
                if max_y < 10 or max_x < 40:
                    self.shutdown()
                    print("Janela do terminal muito pequena. Por favor, redimensione para pelo menos 40x10.")
                    return
                
                # Calcular dimensões das janelas
                chat_height = max_y - 5  
                chat_width = max_x - 22  
                users_width = 20
                
                # Criar janelas com bordas
                self.chat_win = curses.newwin(chat_height, chat_width, 1, 1)
                self.users_win = curses.newwin(chat_height, users_width, 1, chat_width + 1)
                self.input_win = curses.newwin(3, max_x - 2, chat_height + 1, 1)
                self.status_win = curses.newwin(1, max_x, max_y - 1, 0)
                
                # Habilitar rolagem para janela de chat
                self.chat_win.scrollok(True)
                
                # Desenhar bordas iniciais
                self.draw_borders()
                
                # Adicionar usuários padrão para teste
                self.users_in_room = [self.username]
                self.update_users_list()
                
                # Iniciar thread para receber mensagens
                self.running = True
                receiver_thread = threading.Thread(target=self.receive_messages)
                receiver_thread.daemon = True
                receiver_thread.start()
                
                # Solicitar lista de usuários do servidor
                self.request_users_list()
                
                # Atualizar barra de status
                self.update_status()
                
                # Adicionar mensagem de boas-vindas
                self.add_message(f"Bem-vindo ao chat, {self.username}! Você está na sala: {self.current_room}")
                self.add_message("Digite sua mensagem e pressione Enter para enviar")
                self.add_message("Use /join <sala> para mudar de sala")
                self.add_message("Use /whisper <usuário> <mensagem> para enviar mensagens privadas")
                
                # Loop principal de entrada
                self.input_loop()
                
            except Exception as e:
                self.shutdown()
                print(f"Erro na interface: {e}")
                print(traceback.format_exc())
                sys.exit(1)
        except Exception as e:
            print(f"Erro ao inicializar curses: {e}")
            print(traceback.format_exc())
            sys.exit(1)

    def draw_borders(self):
        try:
            # Obter dimensões da tela
            max_y, max_x = self.stdscr.getmaxyx()
            
            # Limpar a tela
            self.stdscr.clear()
            
            # Desenhar borda externa
            self.stdscr.attron(curses.color_pair(6))
            self.stdscr.box()
            self.stdscr.attroff(curses.color_pair(6))
            
            # Desenhar título
            title = f" Cliente de Chat - {self.username} "
            self.stdscr.attron(curses.A_BOLD | curses.color_pair(1))
            self.stdscr.addstr(0, (max_x - len(title)) // 2, title)
            self.stdscr.attroff(curses.A_BOLD | curses.color_pair(1))
            
            # Desenhar título da lista de usuários
            users_title = " Usuários Online "
            chat_width = max_x - 22
            self.stdscr.attron(curses.A_BOLD | curses.color_pair(5))
            self.stdscr.addstr(0, chat_width + 1 + (20 - len(users_title)) // 2, users_title)
            self.stdscr.attroff(curses.A_BOLD | curses.color_pair(5))
            
            # Desenhar título da área de entrada
            input_title = " Mensagem "
            chat_height = max_y - 5
            self.stdscr.attron(curses.A_BOLD | curses.color_pair(4))
            self.stdscr.addstr(chat_height, 1, input_title)
            self.stdscr.attroff(curses.A_BOLD | curses.color_pair(4))
            
            # Atualizar a tela
            self.stdscr.refresh()
        except Exception as e:
            self.shutdown()
            print(f"Erro ao desenhar bordas: {e}")
            print(traceback.format_exc())
            sys.exit(1)

    def update_status(self):
        try:
            self.status_win.clear()
            self.status_win.bkgd(' ', curses.color_pair(8))
            status_text = f" Sala: {self.current_room} | Comandos: /whisper <usuário>, /join <sala>, /blockword <palavra>, /help, /quit "
            self.status_win.addstr(0, 0, status_text)
            self.status_win.refresh()
        except Exception as e:
            print(f"Erro ao atualizar status: {e}")
            print(traceback.format_exc())

    def update_users_list(self):
        try:
            self.users_win.clear()
            
            # Desenhar borda para janela de usuários
            self.users_win.attron(curses.color_pair(6))
            self.users_win.box()
            self.users_win.attroff(curses.color_pair(6))
            
            # Exibir usuários
            for i, user in enumerate(self.users_in_room):
                if i < self.users_win.getmaxyx()[0] - 2:  
                    if user == self.username:
                        self.users_win.addstr(i + 1, 2, user, curses.color_pair(1) | curses.A_BOLD)
                    else:
                        self.users_win.addstr(i + 1, 2, user, curses.color_pair(5))
            
            self.users_win.refresh()
        except Exception as e:
            print(f"Erro ao atualizar lista de usuários: {e}")
            print(traceback.format_exc())

    def update_chat(self):
        try:
            self.chat_win.clear()
            
            # Desenhar borda para janela de chat
            self.chat_win.attron(curses.color_pair(6))
            self.chat_win.box()
            self.chat_win.attroff(curses.color_pair(6))
            
            height, width = self.chat_win.getmaxyx()
            available_height = height - 2  
            available_width = width - 4    
            
            # Mostrar apenas as últimas mensagens que cabem na janela
            display_messages = self.messages[-available_height:] if len(self.messages) > available_height else self.messages
            
            for i, msg in enumerate(display_messages):
                if i < available_height:
                    # Formatar timestamp se presente
                    if isinstance(msg, tuple):
                        timestamp, content = msg
                        timestamp_str = f"[{timestamp.strftime('%H:%M:%S')}] "
                        content_start = len(timestamp_str)
                        self.chat_win.addstr(i + 1, 2, timestamp_str, curses.color_pair(3))
                    else:
                        content = msg
                        content_start = 0
                    
                    # Tratar diferentes tipos de mensagem
                    if isinstance(content, str):
                        if content.startswith("WHISPER"):
                            parts = content[8:].split(":", 1)
                            if len(parts) == 2:
                                sender, text = parts
                                self.chat_win.addstr(i + 1, 2 + content_start, "SUSSURRO ", curses.color_pair(2))
                                self.chat_win.addstr(i + 1, 10 + content_start, f"{sender}:", curses.color_pair(1))
                                self.chat_win.addstr(i + 1, 11 + content_start + len(sender), text, curses.color_pair(4))
                        elif ":" in content:
                            parts = content.split(":", 1)
                            if len(parts) == 2:
                                username, text = parts
                                self.chat_win.addstr(i + 1, 2 + content_start, f"{username}:", curses.color_pair(1))
                                self.chat_win.addstr(i + 1, 3 + content_start + len(username), text, curses.color_pair(4))
                        else:
                            self.chat_win.addstr(i + 1, 2 + content_start, content, curses.color_pair(3))
            
            self.chat_win.refresh()
        except Exception as e:
            print(f"Erro ao atualizar chat: {e}")
            print(traceback.format_exc())

    def update_input(self):
        try:
            self.input_win.clear()
            
            # Desenhar borda para janela de entrada
            self.input_win.attron(curses.color_pair(6))
            self.input_win.box()
            self.input_win.attroff(curses.color_pair(6))
            
            # Adicionar texto de entrada
            self.input_win.addstr(1, 2, self.input_text[:self.input_win.getmaxyx()[1] - 4])
            self.input_win.move(1, 2 + min(self.cursor_pos, self.input_win.getmaxyx()[1] - 4))
            self.input_win.refresh()
        except Exception as e:
            print(f"Erro ao atualizar entrada: {e}")
            print(traceback.format_exc())

    def input_loop(self):
        while self.running:
            try:
                self.update_input()
                
                try:
                    key = self.input_win.getch()
                    
                    if key == curses.KEY_ENTER or key == 10 or key == 13:  
                        if self.input_text.strip():
                            self.process_input(self.input_text)
                            self.input_text = ""
                            self.cursor_pos = 0
                    
                    elif key == curses.KEY_BACKSPACE or key == 127 or key == 8:  
                        if self.cursor_pos > 0:
                            self.input_text = self.input_text[:self.cursor_pos-1] + self.input_text[self.cursor_pos:]
                            self.cursor_pos -= 1
                    
                    elif key == curses.KEY_DC or key == 330 or key == 127:  
                        if self.cursor_pos < len(self.input_text):
                            self.input_text = self.input_text[:self.cursor_pos] + self.input_text[self.cursor_pos+1:]
                    
                    elif key == curses.KEY_LEFT or key == 260:  
                        if self.cursor_pos > 0:
                            self.cursor_pos -= 1
                    
                    elif key == curses.KEY_RIGHT or key == 261:  
                        if self.cursor_pos < len(self.input_text):
                            self.cursor_pos += 1
                    
                    elif key == curses.KEY_HOME or key == 262:  
                        self.cursor_pos = 0
                    
                    elif key == curses.KEY_END or key == 360:  
                        self.cursor_pos = len(self.input_text)
                    
                    elif 32 <= key <= 126:  
                        self.input_text = self.input_text[:self.cursor_pos] + chr(key) + self.input_text[self.cursor_pos:]
                        self.cursor_pos += 1
                    
                    else:
                        self.add_message((datetime.now(), f"Tecla pressionada: {key}"))
                
                except Exception as e:
                    self.add_message((datetime.now(), f"Erro ao processar entrada: {e}"))
            except Exception as e:
                print(f"Erro no loop de entrada: {e}")
                print(traceback.format_exc())
                self.running = False
    
    def process_input(self, text):
        try:
            if text.startswith("/whisper "):
                parts = text[9:].split(" ", 1)
                if len(parts) == 2:
                    target, message = parts
                    self.send_whisper(target, message)
                    self.add_message((datetime.now(), f"SUSSURRO para {target}: {message}"))
            
            elif text.startswith("/join "):
                room = text[6:].strip()
                self.join_room(room)
            
            elif text.startswith("/quit"):
                self.running = False
                self.shutdown()
            
            elif text.startswith("/blockword "):
                word = text[11:].strip()
                if word:
                    self.add_blocked_word(word)
                    self.add_message((datetime.now(), f"Palavra adicionada à blacklist: {word}"))
                else:
                    self.add_message((datetime.now(), "Uso: /blockword <palavra>"))
            
            elif text.startswith("/admin "):
                # Comando para se tornar administrador (com senha)
                password = text[7:].strip()
                if password == "admin123": 
                    self.is_admin = True
                    self.add_message((datetime.now(), "Você agora é um administrador."))
                else:
                    self.add_message((datetime.now(), "Senha incorreta."))
            
            elif text == "/listblocked":
                # Comando para listar palavras bloqueadas (apenas admins)
                if self.is_admin:
                    self.request_blocked_words()
                else:
                    self.add_message((datetime.now(), "Apenas administradores podem listar palavras bloqueadas."))
            
            elif text.startswith("/help"):
                self.add_message((datetime.now(), "Comandos disponíveis:"))
                self.add_message((datetime.now(), "  /join <sala> - Entrar em uma sala específica"))
                self.add_message((datetime.now(), "  /whisper <usuario> <mensagem> - Enviar mensagem privada"))
                self.add_message((datetime.now(), "  /blockword <palavra> - Adicionar palavra à blacklist"))
                if self.is_admin:
                    self.add_message((datetime.now(), "  /listblocked - Listar palavras bloqueadas (admin)"))
                self.add_message((datetime.now(), "  /quit - Sair do chat"))
                self.add_message((datetime.now(), "  /help - Exibir esta ajuda"))
            
            else:
                self.send_message(text)
        except Exception as e:
            print(f"Erro ao processar comando de entrada: {e}")
            print(traceback.format_exc())

    def add_message(self, message):
        try:
            if not isinstance(message, tuple):
                message = (datetime.now(), message)
            self.messages.append(message)
            self.update_chat()
        except Exception as e:
            print(f"Erro ao adicionar mensagem: {e}")
            print(traceback.format_exc())

    def request_users_list(self):
        try:
            self.client_socket.send(json.dumps({
                "type": "get_users",
                "room": self.current_room
            }).encode('utf-8'))
        except Exception as e:
            print(f"Erro ao solicitar lista de usuários: {e}")
            print(traceback.format_exc())
            self.add_message((datetime.now(), f"Erro ao solicitar lista de usuários: {e}"))

    def receive_messages(self):
        buffer = ""
        while self.running:
            try:
                data = self.client_socket.recv(1024).decode('utf-8')
                if not data:
                    break
                
                buffer += data
                
                # Processar objetos JSON completos
                while buffer:
                    try:
                        # Tentar encontrar um objeto JSON completo
                        message, index = self._extract_json(buffer)
                        if message is None:
                            # JSON incompleto, aguardar mais dados
                            break
                        
                        # Processar a mensagem
                        if message["type"] == "message":
                            self.add_message((datetime.now(), message["content"]))
                            
                            # Verificar mensagens de entrada/saída de usuários para atualizar lista
                            content = message["content"]
                            if " entrou " in content:
                                username = content.split(" entrou ")[0]
                                if username not in self.users_in_room:
                                    self.users_in_room.append(username)
                                    self.update_users_list()
                            elif " saiu " in content:
                                username = content.split(" saiu ")[0]
                                if username in self.users_in_room:
                                    self.users_in_room.remove(username)
                                    self.update_users_list()
                        
                        elif message["type"] == "whisper":
                            self.add_message((datetime.now(), f"SUSSURRO {message['sender']}: {message['content']}"))
                        
                        elif message["type"] == "users_list":
                            self.users_in_room = message["users"]
                            self.update_users_list()
                        
                        elif message["type"] == "blocked_words_list":
                            words = message.get("words", [])
                            self.add_message((datetime.now(), f"Lista de palavras bloqueadas ({len(words)}):"))
                            # Mostrar as palavras em grupos de 5 para não poluir o chat
                            for i in range(0, len(words), 5):
                                group = words[i:i+5]
                                self.add_message((datetime.now(), "  " + ", ".join(group)))
                        
                        # Remover a parte processada do buffer
                        buffer = buffer[index:]
                    
                    except ValueError:
                        # Erro de análise JSON, descartar o buffer
                        print(f"Erro ao analisar JSON: {buffer}")
                        buffer = ""
                        break
                
            except Exception as e:
                print(f"Erro ao receber mensagem: {e}")
                print(traceback.format_exc())
                self.running = False
                break
    
    def _extract_json(self, s):
        """Extrair um objeto JSON completo de uma string."""
        # Encontrar a chave de abertura
        start = s.find('{')
        if start == -1:
            return None, 0
        
        # Analisar o JSON
        decoder = json.JSONDecoder()
        try:
            obj, end = decoder.raw_decode(s[start:])
            # Retornar o objeto e a posição final
            return obj, start + end
        except json.JSONDecodeError:
            # Se não foi possível decodificar, pode estar incompleto
            return None, 0

    def send_message(self, message):
        try:
            self.client_socket.send(json.dumps({
                "type": "message",
                "content": message
            }).encode('utf-8'))
        except Exception as e:
            print(f"Erro ao enviar mensagem: {e}")
            print(traceback.format_exc())
            self.add_message((datetime.now(), f"Erro ao enviar mensagem: {e}"))

    def send_whisper(self, target, message):
        try:
            self.client_socket.send(json.dumps({
                "type": "whisper",
                "target": target,
                "content": message
            }).encode('utf-8'))
        except Exception as e:
            print(f"Erro ao enviar sussurro: {e}")
            print(traceback.format_exc())
            self.add_message((datetime.now(), f"Erro ao enviar sussurro: {e}"))

    def join_room(self, room):
        try:
            self.client_socket.send(json.dumps({
                "type": "join_room",
                "room": room
            }).encode('utf-8'))
            self.current_room = room
            self.users_in_room = [self.username]  # Resetar lista de usuários, será atualizada pelo servidor
            self.update_users_list()
            self.update_status()
            self.add_message((datetime.now(), f"Entrando na sala: {room}"))
            
            # Solicitar lista atualizada de usuários para a nova sala
            self.request_users_list()
        except Exception as e:
            print(f"Erro ao entrar na sala: {e}")
            print(traceback.format_exc())
            self.add_message((datetime.now(), f"Erro ao entrar na sala: {e}"))

    def add_blocked_word(self, word):
        try:
            self.client_socket.send(json.dumps({
                "type": "add_blocked_word",
                "word": word
            }).encode('utf-8'))
        except Exception as e:
            print(f"Erro ao adicionar palavra à blacklist: {e}")
            print(traceback.format_exc())
            self.add_message((datetime.now(), f"Erro ao adicionar palavra à blacklist: {e}"))

    def request_blocked_words(self):
        try:
            self.client_socket.send(json.dumps({
                "type": "get_blocked_words"
            }).encode('utf-8'))
        except Exception as e:
            print(f"Erro ao solicitar palavras bloqueadas: {e}")
            print(traceback.format_exc())
            self.add_message((datetime.now(), f"Erro ao solicitar palavras bloqueadas: {e}"))

    def shutdown(self):
        self.running = False
        
        # Restaurar configurações do terminal
        if self.stdscr:
            try:
                curses.curs_set(1)  # Mostrar cursor
                self.stdscr.keypad(False)
                curses.nocbreak()
                curses.echo()
                curses.endwin()
            except Exception as e:
                print(f"Erro ao restaurar configurações do terminal: {e}")
                print(traceback.format_exc())
        
        # Fechar socket
        try:
            self.client_socket.close()
        except Exception as e:
            print(f"Erro ao fechar socket: {e}")
            print(traceback.format_exc())

if __name__ == "__main__":
    try:
        if len(sys.argv) < 2:
            print("Uso: python client.py <nome_de_usuario>")
            sys.exit(1)
        
        username = sys.argv[1]
        client = ChatClient()
        
        if client.connect(username):
            try:
                client.start_ui()
            except KeyboardInterrupt:
                pass
            except Exception as e:
                print(f"Erro no cliente: {e}")
                print(traceback.format_exc())
            finally:
                client.shutdown()
        else:
            print("Falha ao conectar ao servidor.")
    except Exception as e:
        print(f"Erro não tratado: {e}")
        print(traceback.format_exc()) 