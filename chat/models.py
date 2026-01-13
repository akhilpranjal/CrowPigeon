from django.db import models
from datetime import datetime

# Create your models here.

class Room(models.Model):
    name = models.CharField(max_length=100)

class Message(models.Model):
    room = models.ForeignKey(Room, on_delete=models.CASCADE)
    user = models.CharField(max_length=100)
    content = models.TextField()
    timestamp = models.DateTimeField(auto_now_add=True)
