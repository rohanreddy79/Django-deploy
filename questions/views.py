from cmath import log
from django.shortcuts import redirect, render

from questions.models import Answers, Question
from rest_framework.authentication import SessionAuthentication
from rest_framework.decorators import api_view, authentication_classes
from rest_framework.response import Response
# Create your views here.
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.contrib.auth import authenticate , login
from django.http import HttpResponse


from django.contrib import messages
def login_view(request):
    if request.method == 'POST':
        email = request.POST.get('email')
        password = request.POST.get('password')
        user_obj= User.objects.filter(username = email)
        if not user_obj.exists  ():
            messages.info(request, 'Account not found')
            return redirect('/register/')

        user_obj = authenticate(username =email ,password = password)
        
        if user_obj:
            login(request , user_obj)
            return redirect('/dashboard/')

        messages.info(request, 'Invalid password')
        return redirect('/')
        
    return render(request , 'login.html')

def register_view(request):

    if request.method == 'POST':
        email = request.POST.get('email')
        password = request.POST.get('password')

        user_obj= User.objects.filter(username = email)

        if user_obj.exists():
            messages.info(request, 'Username is already taken')
            return redirect('/register/')

        user_obj = User.objects.create(username = email)
        user_obj.set_password(password)
        user_obj.save()
        messages.info(request, 'Account created')
        return redirect('/')

    return render(request , 'register.html')




@login_required
def dashboard(request):

    return render(request , 'dashboard.html')


@login_required
def create_poll(request):

    if request.method == 'POST':
        question = request.POST.get('question')
        answers = request.POST.getlist('answers')

        question_obj = Question.objects.create(
            user = request.user,
            question_text = question
        )

        for answer in answers:
            Answers.objects.create(answer_text = answer , question = question_obj)


        messages.info(request, 'Your Poll Has been created')

        return redirect('/create_poll/')

    return render(request , 'create_poll.html')



@login_required
def see_answers(request):
    questions = Question.objects.filter(user = request.user)
    return render(request ,'see_answers.html' ,{'questions' : questions})


class CsrfSessionAuthentication(SessionAuthentication):
    """Session authentication that enforces the CSRF check for anonymous voters too.

    DRF's SessionAuthentication only checks CSRF for logged-in users; the public vote page
    is anonymous, so the token sent in the X-CSRFToken header is validated unconditionally.
    """

    def authenticate(self, request):
        self.enforce_csrf(request)
        return super().authenticate(request)


@api_view(['POST'])
@authentication_classes([CsrfSessionAuthentication])
def save_question_result(request):
    data = request.data
    question_uid = data.get('question_uid')
    answer_uid = data.get('answer_uid')

    if question_uid is None or answer_uid is None:
        payload = {'data' : 'both question uid and answer uid are required' , 'status' : False}

        return Response(payload)

    question_obj = Question.objects.get(uid = question_uid)
    answer_obj  = Answers.objects.get(uid = answer_uid)
    answer_obj.counter += 1
    answer_obj.save()

    payload = {'data' : question_obj.calculate_percentage() , 'status' : True}

    return Response(payload)





def question_detail(request , question_uid):
    try:
        question_obj = Question.objects.get(uid = question_uid)
        context = {'question' : question_obj}
        return render(request , 'question.html' , context)

    except Exception as e :
        print(e)
        return redirect('/')
