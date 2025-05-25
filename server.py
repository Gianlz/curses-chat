import socket
import threading
import json
import re
import os

class ChatServer:
    def __init__(self, host='localhost', port=9999):
        self.host = host
        self.port = port
        self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.clients = {}  # {client_socket: {"username": username, "room": room}}
        self.rooms = {"general": set()}  # Sala padrão
        self.bad_words = self.load_bad_words("palavras_bloqueadas.txt")
        print(f"Carregadas {len(self.bad_words)} palavras para a blacklist")

    def load_bad_words(self, filename):
        """Carrega a lista de palavras impróprias do arquivo."""
        bad_words = []
        try:
            if os.path.exists(filename):
                with open(filename, 'r', encoding='utf-8') as file:
                    bad_words = [word.strip().lower() for word in file.readlines() if word.strip()]
                print(f"Arquivo de blacklist carregado: {filename}")
            else:
                print(f"Arquivo de blacklist não encontrado: {filename}")
        except Exception as e:
            print(f"Erro ao carregar a blacklist: {e}")
        return bad_words
        
    def censor_message(self, message):
        """Censura palavras impróprias na mensagem."""
        if not self.bad_words:
            return message

        words = re.findall(r'\b\w+\b|\W+', message)

        for i, word in enumerate(words):
            if word.lower() in self.bad_words:
                words[i] = '*' * len(word)
        
        return ''.join(words)

    def start(self):
        self.server_socket.bind((self.host, self.port))
        self.server_socket.listen(5)
        print(f"Servidor iniciado em {self.host}:{self.port}")
        
        try:
            while True:
                client_socket, address = self.server_socket.accept()
                print(f"Conexão de {address} foi estabelecida!")
                
                # Iniciar uma nova thread para cada cliente
                client_thread = threading.Thread(target=self.handle_client, args=(client_socket,))
                client_thread.daemon = True
                client_thread.start()
        except KeyboardInterrupt:
            print("Servidor desligando...")
        finally:
            self.server_socket.close()

    def handle_client(self, client_socket):
        try:
            # Obter nome de usuário do cliente
            username_data = client_socket.recv(1024).decode('utf-8')
            username = json.loads(username_data)["username"]
            
            # Adicionar cliente à sala geral por padrão
            self.clients[client_socket] = {"username": username, "room": "general"}
            self.rooms["general"].add(client_socket)
            
            # Notificar todos na sala
            self.broadcast(f"{username} entrou na sala geral!", "general")
            
            # Enviar lista de usuários atual para o novo cliente
            self.send_users_list(client_socket, "general")
            
            while True:
                data = client_socket.recv(1024).decode('utf-8')
                if not data:
                    break
                
                message = json.loads(data)
                
                if message["type"] == "message":
                    room = self.clients[client_socket]["room"]
                    sender = self.clients[client_socket]["username"]
                    
                    # Censurar a mensagem antes de enviar
                    censored_content = self.censor_message(message['content'])
                    self.broadcast(f"{sender}: {censored_content}", room)
                
                elif message["type"] == "whisper":
                    target = message["target"]
                    sender = self.clients[client_socket]["username"]
                    
                    # Censurar a mensagem privada antes de enviar
                    censored_content = self.censor_message(message['content'])
                    self.whisper(sender, target, censored_content)
                
                elif message["type"] == "join_room":
                    self.change_room(client_socket, message["room"])
                
                elif message["type"] == "get_users":
                    room = message.get("room", self.clients[client_socket]["room"])
                    self.send_users_list(client_socket, room)
                    
                elif message["type"] == "add_blocked_word":
                    word = message.get("word", "").strip().lower()
                    if word and word not in self.bad_words:
                        self.add_bad_word(word)
                        username = self.clients[client_socket]["username"]
                        room = self.clients[client_socket]["room"]
                        self.broadcast(f"Sistema: {username} adicionou uma palavra à blacklist.", room)
                
                elif message["type"] == "get_blocked_words":
                    self.send_blocked_words_list(client_socket)
        
        except Exception as e:
            print(f"Erro: {e}")
        finally:
            self.remove_client(client_socket)

    def broadcast(self, message, room):
        for client in self.rooms.get(room, set()):
            try:
                client.send(json.dumps({"type": "message", "content": message}).encode('utf-8'))
            except:
                self.remove_client(client)

    def whisper(self, sender, target, message):
        for client, info in self.clients.items():
            if info["username"] == target:
                try:
                    client.send(json.dumps({
                        "type": "whisper", 
                        "sender": sender, 
                        "content": message
                    }).encode('utf-8'))
                    return True
                except:
                    self.remove_client(client)
                    return False
        return False

    def change_room(self, client_socket, new_room):
        if client_socket not in self.clients:
            return
        
        # Criar sala se não existir
        if new_room not in self.rooms:
            self.rooms[new_room] = set()
        
        # Remover da sala antiga
        old_room = self.clients[client_socket]["room"]
        if old_room in self.rooms and client_socket in self.rooms[old_room]:
            self.rooms[old_room].remove(client_socket)
            username = self.clients[client_socket]["username"]
            self.broadcast(f"{username} saiu da sala.", old_room)
        
        # Adicionar à nova sala
        self.rooms[new_room].add(client_socket)
        self.clients[client_socket]["room"] = new_room
        username = self.clients[client_socket]["username"]
        self.broadcast(f"{username} entrou na sala!", new_room)
        
        # Enviar lista de usuários atualizada para o cliente
        self.send_users_list(client_socket, new_room)

    def send_users_list(self, client_socket, room):
        if room not in self.rooms:
            return
            
        users = []
        for client, info in self.clients.items():
            if info["room"] == room:
                users.append(info["username"])
                
        try:
            client_socket.send(json.dumps({
                "type": "users_list",
                "users": users
            }).encode('utf-8'))
        except:
            self.remove_client(client_socket)

    def remove_client(self, client_socket):
        if client_socket in self.clients:
            username = self.clients[client_socket]["username"]
            room = self.clients[client_socket]["room"]
            
            # Remover da sala
            if room in self.rooms and client_socket in self.rooms[room]:
                self.rooms[room].remove(client_socket)
                self.broadcast(f"{username} saiu do chat.", room)
            
            # Remover dos clientes
            del self.clients[client_socket]
            
            # Fechar socket
            try:
                client_socket.close()
            except:
                pass

    def add_bad_word(self, word):
        """Adiciona uma palavra à blacklist e atualiza o arquivo."""
        if word not in self.bad_words:
            self.bad_words.append(word)
            try:
                with open("palavras_bloqueadas.txt", "a", encoding="utf-8") as file:
                    file.write(f"\n{word}")
                print(f"Palavra adicionada à blacklist: {word}")
            except Exception as e:
                print(f"Erro ao salvar palavra na blacklist: {e}")

    def send_blocked_words_list(self, client_socket):
        """Envia a lista de palavras bloqueadas para o cliente."""
        try:
            client_socket.send(json.dumps({
                "type": "blocked_words_list",
                "words": self.bad_words
            }).encode('utf-8'))
            print(f"Lista de palavras bloqueadas enviada para o cliente.")
        except Exception as e:
            print(f"Erro ao enviar lista de palavras bloqueadas: {e}")
            self.remove_client(client_socket)

if __name__ == "__main__":
    server = ChatServer()
    server.start() 