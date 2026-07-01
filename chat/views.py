from django.shortcuts import render, redirect
from django.contrib.auth.hashers import make_password, check_password
from django.views.decorators.http import require_POST
from channels.layers import get_channel_layer
from asgiref.sync import async_to_sync

from .models import Room, Message, RoomMember


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def is_approved_member(request, room):
    """Return True if the current session user is an approved member of the room."""
    return RoomMember.objects.filter(
        room=room,
        session_key=request.session.session_key,
        status='approved',
    ).exists()


# ---------------------------------------------------------------------------
# Views
# ---------------------------------------------------------------------------

def home(request):
    """Landing page — handles room creation and join requests.

    GET  → If the user already has a valid session for a room, redirect there.
    POST → Create a new room or submit a join request for an existing one.
    """
    # Ensure the session exists so we have a session_key to work with.
    if not request.session.session_key:
        request.session.create()

    # --- GET: Resume an existing session if possible ---
    if request.method != 'POST':
        room_id = request.session.get('room_id')
        username = request.session.get('username')

        if room_id and username:
            try:
                room = Room.objects.get(id=room_id)
            except Room.DoesNotExist:
                request.session.flush()
                return render(request, 'home.html')

            member = RoomMember.objects.filter(
                room=room,
                session_key=request.session.session_key,
            ).first()

            if member is None:
                request.session.flush()
                return render(request, 'home.html')

            if member.status == 'approved':
                return redirect('room')
            if member.status in {'pending', 'rejected'}:
                return redirect('waiting')

        return render(request, 'home.html')

    # --- POST: Create or join a room ---
    username = (request.POST.get('username') or '').strip()
    room_name = (request.POST.get('room') or '').strip()
    password = request.POST.get('password') or ''
    action = (request.POST.get('action') or 'join').strip().lower()

    if not username or not room_name or not password:
        return render(request, 'home.html', {
            'error': 'Username, room name, and password are required.',
        })

    request.session['username'] = username

    # -- Create a new room --
    if action == 'create':
        if Room.objects.filter(name__iexact=room_name).exists():
            return render(request, 'home.html', {
                'error': 'A room with this name already exists. Try joining it instead.',
            })

        room = Room.objects.create(
            name=room_name,
            password=make_password(password),
            owner_session=request.session.session_key,
        )
        RoomMember.objects.create(
            room=room,
            username=username,
            session_key=request.session.session_key,
            status='approved',
        )

        request.session['room_id'] = room.id
        request.session['room_name'] = room.name
        return redirect('room')

    # -- Join an existing room --
    room = Room.objects.filter(name=room_name).first()

    if room is None:
        return render(request, 'home.html', {
            'error': 'Room not found. Create it first or check the room name.',
        })

    if not check_password(password, room.password):
        return render(request, 'home.html', {
            'error': 'Wrong room password.',
        })

    member, created = RoomMember.objects.get_or_create(
        room=room,
        session_key=request.session.session_key,
        defaults={'username': username, 'status': 'pending'},
    )

    if not created:
        member.username = username
        if member.status != 'approved':
            member.status = 'pending'
        member.save(update_fields=['username', 'status'])

    request.session['room_id'] = room.id
    request.session['room_name'] = room.name

    # Notify connected clients about the updated pending-request count.
    if member.status == 'pending':
        pending_count = RoomMember.objects.filter(room=room, status='pending').count()
        try:
            channel_layer = get_channel_layer()
            async_to_sync(channel_layer.group_send)(
                f'chat_{room.id}',
                {'type': 'pending_count', 'count': pending_count},
            )
        except Exception:
            pass  # Non-critical; badge will update on next page load

    if member.status == 'approved':
        return redirect('room')
    return redirect('waiting')


def waiting(request):
    """Waiting room — shown while a join request is pending or after rejection."""
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
        session_key=request.session.session_key,
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
    """Main chat room view — only accessible to approved members."""
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

    # Only fetch pending requests if the current user owns the room.
    owner_pending_requests = []
    if is_owner:
        owner_pending_requests = RoomMember.objects.filter(
            room=chat_room, status='pending',
        ).order_by('requested_at')

    approved_members = RoomMember.objects.filter(
        room=chat_room, status='approved',
    ).order_by('username')

    # Resolve the owner's display name for the crown icon in the UI.
    owner_member = RoomMember.objects.filter(
        room=chat_room,
        session_key=chat_room.owner_session,
        status='approved',
    ).first()
    owner_username = owner_member.username if owner_member else ''

    return render(request, 'room.html', {
        'username': request.session['username'],
        'room': chat_room,
        'messages': messages,
        'is_owner': is_owner,
        'owner_username': owner_username,
        'owner_pending_requests': owner_pending_requests,
        'approved_members': approved_members,
    })


def inbox(request):
    """Owner inbox — lists pending join requests across all rooms the user owns."""
    if not request.session.session_key:
        return redirect('/')

    rooms = Room.objects.filter(owner_session=request.session.session_key)
    if not rooms.exists():
        return redirect('home')

    current_room = None
    room_id = request.session.get('room_id')
    if room_id:
        current_room = rooms.filter(id=room_id).first()

    pending_requests = RoomMember.objects.filter(room__in=rooms, status='pending')

    return render(request, 'inbox.html', {
        'requests': pending_requests,
        'current_room': current_room,
    })


@require_POST
def approve(request, member_id):
    """Approve a pending room-join request (owner only)."""
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
    """Reject a pending room-join request (owner only)."""
    member = RoomMember.objects.filter(id=member_id).first()
    if member is None:
        return redirect('inbox')

    if member.room.owner_session != request.session.session_key:
        return redirect('/')

    member.status = 'rejected'
    member.save()
    return redirect('inbox')


def leave_room(request):
    """Clear room session data and redirect to home."""
    for key in ('room_id', 'room_name', 'username'):
        request.session.pop(key, None)
    return redirect('home')
