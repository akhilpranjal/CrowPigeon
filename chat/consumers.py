import json
import logging
from channels.generic.websocket import AsyncWebsocketConsumer
from channels.db import database_sync_to_async
from .models import Room, Message, RoomMember

logger = logging.getLogger(__name__)

class ChatConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        session = self.scope.get('session', {})
        self.room_id = session.get('room_id')
        self.room_group_name = f'chat_{self.room_id}'

        if not self.room_id:
            await self.close()
            return
        
        try:
            room = await self.get_room(self.room_id)
            session_key = session.session_key if hasattr(session, 'session_key') else None
            
            if not session_key:
                await self.close()
                return
            
            is_member = await self.check_membership(room, session_key)

            if not is_member:
                await self.close()
                return
            
            await self.channel_layer.group_add(
                self.room_group_name,
                self.channel_name
            )

            await self.accept()
        except Exception:
            logger.exception('WebSocket connect failed for room %d', self.room_id)
            await self.close()

    @database_sync_to_async
    def get_room(self, room_id):
        return Room.objects.get(id=room_id)
    
    @database_sync_to_async
    def check_membership(self, room, session_key):
        return RoomMember.objects.filter(
            room=room,
            session_key=session_key,
            status='approved'
        ).exists()
    
    @database_sync_to_async
    def save_message(self, room, username, content):
        return Message.objects.create(
            room=room,
            user=username,
            content=content
        )

    async def disconnect(self, close_code):
        await self.channel_layer.group_discard(
            self.room_group_name,
            self.channel_name
        )

    async def receive(self, text_data):
        try:
            data = json.loads(text_data)
            message = data.get('message')

            if not isinstance(message, str) or not message.strip():
                return
            
            session = self.scope.get('session', {})
            username = session.get('username')

            if not username:
                return

            room = await self.get_room(self.room_id)
            saved_message = await self.save_message(room, username, message)
            
            await self.channel_layer.group_send(
                self.room_group_name,
                {
                    'type': 'chat_message',
                    'message': message,
                    'username': username,
                    'timestamp': saved_message.timestamp.strftime('%H:%M')
                }
            )
        except Exception:
            logger.exception('WebSocket receive failed for room %d', self.room_id)
    
    async def chat_message(self, event):
        await self.send(text_data=json.dumps({
            'message': event['message'],
            'username': event['username'],
            'timestamp': event.get('timestamp')
        })) 