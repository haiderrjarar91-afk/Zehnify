from django.urls import path
from django.contrib.auth import views as auth_views
from ZehnifyApp import views

urlpatterns = [
    path('', views.home, name='home_page'),
    path('subjects/<int:subject_id>/', views.sub_details, name='subject_detail'),
    path('chapter/<int:chapter_id>/', views.chapterdetail, name='details_page'),
    path('login/', auth_views.LoginView.as_view(template_name='zehnify/login.html'), name='login_page'),
    path('logout/', auth_views.LogoutView.as_view(), name='logout_page'),
    path('signup/', views.signup, name='signup_page'),
    path('chapter/<int:chapter_id>/practice/', views.practice, name='practice_page'),
    path('chapter/<int:chapter_id>/videos/', views.videos, name='video_page'),
    path('chapter/<int:chapter_id>/exam/', views.Exam, name='exam_page'),
    path('chapter/<int:chapter_id>/exam/review/<int:attempt_id>/', views.exam_review, name='exam_review'),
    path('video/<int:video_id>/toggle-watched/', views.toggle_video_watched, name='toggle_video_watched'),
    path('lecture/<int:video_id>/', views.watch_lecture, name='watch_lecture'),
    path('notes/<int:chapter_id>/', views.notes, name='notes_page'),
    path('chapter/<int:chapter_id>/mixed-practice/', views.mixed_practice_setup, name='mixed_practice_setup'),
    path('mixed-practice/<int:attempt_id>/', views.mixed_practice_session, name='mixed_practice_session'),
    path('mixed-practice/<int:attempt_id>/review/', views.mixed_practice_review, name='mixed_practice_review'),
]