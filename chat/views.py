from django.shortcuts import render, redirect
from .models import Room, Message
from django.http import JsonResponse, HttpResponse

# Create your views here.

def home(request):
    if request.method == "POST":
        username = request.POST.get('username')
        room_name = request.POST.get('room')

        room, created = Room.objects.get_or_create(name=room_name)

        request.session['username'] = username
        request.session['room'] = room.name

        return redirect('/room/')
    return render(request, 'home.html')


def room(request):
    username = request.session.get('username')
    room_name = request.session.get('room')

    room = Room.objects.get(name=room_name)

    if request.method=='POST':
        content = request.POST.get('message')
        Message.objects.create(
            room=room,
            user=username,
            content=content
        )
        return redirect('/room/')
    
    messages = Message.objects.filter(room=room).order_by('timestamp')

    return render(request, 'room.html', {
        'username':username,
        'room':room,
        'messages':messages
    })