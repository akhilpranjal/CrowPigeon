from django.shortcuts import render, redirect
from .models import Room, Message, RoomMember
from django.http import JsonResponse, HttpResponse
from django.contrib.auth.hashers import make_password, check_password

# Create your views here.

def home(request):
    if request.method == "POST":
        username = request.POST.get('username')
        room_name = request.POST.get('room')
        password = request.POST.get('password')

        request.session['username'] = username

        room = Room.objects.filter(name=room_name).first()

        if room is None:
            if not request.session.session_key:
                request.session.create()

            Room.objects.create(
                name = room_name,
                password = make_password(password),
                owner_session = request.session.session_key
            )

            RoomMember.objects.create(
                room=room,
                username=username,
                session_key=request.session.session_key,
                status='approved'

            )

            request.session['room'] = room.name
            return redirect('room')
        else:
            if (check_password(password, room.password)):
                RoomMember.objects.get_or_create(
                    room=room,
                    session_key=request.session.session_key,
                    defaults={
                        'username': username,
                        'status': 'pending'
                    }
                )


                request.session['room'] = room.name
                return redirect('waiting')
            else:
                return render(request, 'home.html', {
                    'error': 'Wrong room password' 
                })

    
    return render(request, 'home.html')


def room(request):

    if 'username' not in request.session or 'room' not in request.session:
        return redirect('/')
    # print(request.session.items())

    chat_room = Room.objects.get(name=request.session['room'])

    if request.method=='POST':
        content = request.POST.get('message')
        Message.objects.create(
            room=chat_room,
            user=request.session['username'],
            content=content
        )
        return redirect('room')
    
    messages = Message.objects.filter(room=chat_room).order_by('timestamp')

    return render(request, 'room.html', {
        'username':request.session['username'],
        'room':chat_room,
        'messages':messages
    })