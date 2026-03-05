from django.shortcuts import render, redirect
from .models import Room, Message, RoomMember
from django.http import HttpResponse
from django.contrib.auth.hashers import make_password, check_password
from django.views.decorators.http import require_POST

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
        username = (request.POST.get('username') or '').strip()
        room_name = (request.POST.get('room') or '').strip()
        password = request.POST.get('password') or ''
        action = (request.POST.get('action') or 'join').strip().lower()

        if not username or not room_name or not password:
            return render(request, 'home.html', {
                'error': 'Username, room name, and password are required.'
            })

        request.session['username'] = username

        if action == 'create':
            # Check if exact room with this name and password already exists
            existing_room = Room.objects.filter(name=room_name).filter(password=make_password(password)).first()
            if existing_room:
                return render(request, 'home.html', {
                    'error': 'A room with this name and password already exists. Join it instead.'
                })

            room = Room.objects.create(
                name=room_name,
                password=make_password(password),
                owner_session=request.session.session_key
            )

            RoomMember.objects.create(
                room=room,
                username=username,
                session_key=request.session.session_key,
                status='approved'
            )

            request.session['room_id'] = room.id
            request.session['room_name'] = room.name
            return redirect('room')

        room = Room.objects.filter(name=room_name).first()
        
        if room is None:
            return render(request, 'home.html', {
                'error': 'Room not found. Create it first or check the room name.'
            })

        if check_password(password, room.password):
            member, created = RoomMember.objects.get_or_create(
                room=room,
                session_key=request.session.session_key,
                defaults={
                    'username': username,
                    'status': 'pending'
                }
            )

            if not created:
                member.username = username
                if member.status != 'approved':
                    member.status = 'pending'
                member.save(update_fields=['username', 'status'])

            request.session['room_id'] = room.id
            request.session['room_name'] = room.name
            if member.status == 'approved':
                return redirect('room')
            return redirect('waiting')

        else:
                return render(request, 'home.html', {
                    'error': 'Wrong room password' 
                })

    return render(request, 'home.html')



def waiting(request):
    room_id = request.session.get('room_id')
    if not room_id:
        return redirect('/')

    try:
        room = Room.objects.get(id=room_id)
    except Room.DoesNotExist:
        request.session.flush()
        return redirect('/')

    member = RoomMember.objects.filter(
        room=room,
        session_key=request.session.session_key
    ).first()

    if member is None:
        request.session.flush()
        return redirect('/')

    if member.status == 'approved':
        return redirect('room')
    if member.status == 'rejected':
        return render(request, 'waiting.html', {'rejected': True})
    
    return render(request, 'waiting.html')



def room(request):
    if 'username' not in request.session or 'room_id' not in request.session:
        return redirect('/')
    room_id = request.session['room_id']
    try:
        chat_room = Room.objects.get(id=room_id)
    except Room.DoesNotExist:
        request.session.flush()
        return redirect('/')


    if not is_approved_member(request, chat_room):
        return redirect('waiting')
    
    messages = Message.objects.filter(room=chat_room).order_by('timestamp')
    is_owner = chat_room.owner_session == request.session.session_key
    owner_pending_requests = []

    if is_owner:
        owner_pending_requests = RoomMember.objects.filter(
            room=chat_room,
            status='pending'
        ).order_by('requested_at')

    approved_members = RoomMember.objects.filter(
        room=chat_room,
        status='approved'
    ).order_by('username')

    return render(request, 'room.html', {
        'username':request.session['username'],
        'room':chat_room,
        'messages':messages,
        'is_owner': is_owner,
        'owner_pending_requests': owner_pending_requests,
        'approved_members': approved_members,
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


@require_POST
def approve(request, member_id):
    member = RoomMember.objects.filter(id=member_id).first()
    if member is None:
        return redirect('inbox')

    if member.room.owner_session != request.session.session_key:
        return redirect('/')

    member.status = 'approved'
    member.save()
    return redirect('inbox')


@require_POST
def reject(request, member_id):
    member = RoomMember.objects.filter(id=member_id).first()
    if member is None:
        return redirect('inbox')

    if member.room.owner_session != request.session.session_key:
        return redirect('/')

    member.status = 'rejected'
    member.save()
    return redirect('inbox')
