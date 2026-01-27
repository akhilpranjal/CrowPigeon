from django.shortcuts import render, redirect
from .models import Room, Message, RoomMember
from django.http import HttpResponse
from django.contrib.auth.hashers import make_password, check_password

def is_approved_member(request, room):
    return RoomMember.objects.filter(
        room=room,
        session_key=request.session.session_key,
        status='approved'
    ).exists()


def home(request):
    if not request.session.session_key:
        request.session.create()

    if request.method == "POST":
        username = request.POST.get('username')
        room_name = request.POST.get('room')
        password = request.POST.get('password')

        request.session['username'] = username

        room = Room.objects.filter(name=room_name).first()

        if room is None:
            room = Room.objects.create(
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



def waiting(request):
    room_name = request.session.get('room')

    if not room_name:
        return redirect('/')
    
    room = Room.objects.get(name=room_name)

    member = RoomMember.objects.get(
        room=room,
        session_key=request.session.session_key
    )

    if member.status == 'approved':
        return redirect('room')
    if member.status == 'rejected':
        return render(request, 'waiting.html', {'rejected': True})
    
    return render(request, 'waiting.html')



def room(request):
    if 'username' not in request.session or 'room' not in request.session:
        return redirect('/')

    chat_room = Room.objects.get(name=request.session['room'])

    if not is_approved_member(request, chat_room):
        return redirect('waiting')
    
    messages = Message.objects.filter(room=chat_room).order_by('timestamp')

    return render(request, 'room.html', {
        'username':request.session['username'],
        'room':chat_room,
        'messages':messages
    })



def inbox(request):
    if not request.session.session_key:
        return redirect('/')

    rooms = Room.objects.filter(
        owner_session=request.session.session_key
    )

    if not rooms.exists():
        return HttpResponse("Not authorized", status=403)

    requests = RoomMember.objects.filter(
        room__in=rooms,
        status='pending'
    )

    return render(request, 'inbox.html', {'requests': requests})


def approve(request, member_id):
    member = RoomMember.objects.get(id=member_id)

    if member.room.owner_session != request.session.session_key:
        return redirect('/')

    member.status = 'approved'
    member.save()
    return redirect('inbox')


def reject(request, member_id):
    member = RoomMember.objects.get(id=member_id)

    if member.room.owner_session != request.session.session_key:
        return redirect('/')

    member.status = 'rejected'
    member.save()
    return redirect('inbox')
