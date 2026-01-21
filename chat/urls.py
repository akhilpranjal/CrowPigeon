from django.urls import path
from . import views

urlpatterns = [
    path('', views.home, name='home'),
    path('room/', views.room, name='room'),
    path('waiting/', views.waiting, name='waiting'),
    path('inbox/', views.inbox, name='inbox'),
    path('approve/<int:member_id>/', views.approve, name='approve'),
    path('reject/<int:member_id>/', views.reject, name='reject'),
]