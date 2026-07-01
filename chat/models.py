from django.db import models


class Room(models.Model):
    """A password-protected chat room created by a session owner."""
    name = models.CharField(max_length=100)
    password = models.CharField(max_length=255)
    owner_session = models.CharField(max_length=255)

    def __str__(self):
        return self.name


class Message(models.Model):
    """A single chat message belonging to a room."""
    room = models.ForeignKey(Room, on_delete=models.CASCADE)
    user = models.CharField(max_length=100)
    content = models.TextField()
    timestamp = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f'{self.user}: {self.content[:40]}'


class RoomMember(models.Model):
    """Tracks a user's membership request and approval status for a room."""
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('approved', 'Approved'),
        ('rejected', 'Rejected'),
    ]

    room = models.ForeignKey(Room, on_delete=models.CASCADE)
    username = models.CharField(max_length=100)
    session_key = models.CharField(max_length=255)
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='pending')
    requested_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f'{self.username} ({self.status}) in {self.room}'
