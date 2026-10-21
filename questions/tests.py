from django.contrib.auth.models import User
from django.test import Client, TestCase

from questions.models import Answers, Question

VOTE_API = '/api/save_question_result/'


class PollFlowTests(TestCase):
    """Drives the app through the Django test client: register -> login -> create poll -> vote -> results."""

    email = 'alice@example.com'
    password = 'correct-horse-battery-staple'

    def register_and_login(self):
        response = self.client.post('/register/', {'email': self.email, 'password': self.password})
        self.assertRedirects(response, '/', fetch_redirect_response=False)
        self.assertTrue(User.objects.filter(username=self.email).exists())

        response = self.client.post('/', {'email': self.email, 'password': self.password})
        self.assertRedirects(response, '/dashboard/', fetch_redirect_response=False)
        return User.objects.get(username=self.email)

    def make_poll(self):
        user = self.register_and_login()
        question = Question.objects.create(user=user, question_text='Tabs or spaces?')
        tabs = Answers.objects.create(question=question, answer_text='Tabs')
        spaces = Answers.objects.create(question=question, answer_text='Spaces')
        return question, tabs, spaces

    @staticmethod
    def vote(client, question, answer, **extra):
        payload = {'question_uid': str(question.uid), 'answer_uid': str(answer.uid)}
        return client.post(VOTE_API, payload, content_type='application/json', **extra)

    def test_login_page_renders_the_form(self):
        response = self.client.get('/')
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'login.html')
        self.assertContains(response, 'name="password"')

    def test_login_with_wrong_password_is_rejected(self):
        self.register_and_login()
        self.client.logout()
        response = self.client.post('/', {'email': self.email, 'password': 'nope'})
        self.assertRedirects(response, '/', fetch_redirect_response=False)
        self.assertNotIn('_auth_user_id', self.client.session)

    def test_login_with_unknown_account_redirects_to_register(self):
        response = self.client.post('/', {'email': 'nobody@example.com', 'password': 'x'})
        self.assertRedirects(response, '/register/', fetch_redirect_response=False)

    def test_full_poll_flow(self):
        user = self.register_and_login()

        response = self.client.post(
            '/create_poll/', {'question': 'Tabs or spaces?', 'answers': ['Tabs', 'Spaces']}
        )
        self.assertRedirects(response, '/create_poll/')
        question = Question.objects.get(user=user)
        self.assertEqual(question.question_text, 'Tabs or spaces?')
        self.assertEqual(
            sorted(question.answers.values_list('answer_text', flat=True)), ['Spaces', 'Tabs']
        )
        tabs = question.answers.get(answer_text='Tabs')

        # The vote page is public: an anonymous visitor loads it, which sets the CSRF cookie,
        # and the page's JavaScript posts the token back in the X-CSRFToken header.
        voter = Client()
        page = voter.get(f'/question/{question.uid}/')
        self.assertEqual(page.status_code, 200)
        self.assertContains(page, 'Tabs or spaces?')
        self.assertContains(page, 'X-CSRFToken')
        token = voter.cookies['csrftoken'].value

        response = self.vote(voter, question, tabs, HTTP_X_CSRFTOKEN=token)
        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertTrue(body['status'])
        self.assertEqual(body['data'], question.calculate_percentage())
        self.assertEqual(sorted(body['data']), [0, 100])
        tabs.refresh_from_db()
        self.assertEqual(tabs.counter, 1)

        # The owner sees the results page with the per-question link.
        response = self.client.get('/see_answers/')
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'see_answers.html')
        self.assertContains(response, 'Tabs or spaces?')
        self.assertContains(response, f'/question/{question.uid}')

    def test_vote_api_rejects_requests_without_a_csrf_token(self):
        question, tabs, _ = self.make_poll()
        strict = Client(enforce_csrf_checks=True)
        response = self.vote(strict, question, tabs)
        self.assertEqual(response.status_code, 403)
        tabs.refresh_from_db()
        self.assertEqual(tabs.counter, 0)

    def test_vote_api_accepts_the_csrf_token_under_strict_checks(self):
        question, tabs, _ = self.make_poll()
        strict = Client(enforce_csrf_checks=True)
        strict.get(f'/question/{question.uid}/')
        token = strict.cookies['csrftoken'].value
        response = self.vote(strict, question, tabs, HTTP_X_CSRFTOKEN=token)
        self.assertEqual(response.status_code, 200)
        tabs.refresh_from_db()
        self.assertEqual(tabs.counter, 1)

    def test_vote_api_requires_both_uids(self):
        question, tabs, _ = self.make_poll()
        response = self.client.post(
            VOTE_API, {'question_uid': str(question.uid)}, content_type='application/json'
        )
        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.json()['status'])
        tabs.refresh_from_db()
        self.assertEqual(tabs.counter, 0)

    def test_percentages_are_zero_before_any_vote(self):
        question, tabs, _ = self.make_poll()
        self.assertEqual(question.calculate_percentage(), [0, 0])
        self.assertEqual(tabs.calculate_percentage(), 0)

    def test_authenticated_pages_redirect_anonymous_visitors_to_login(self):
        for path in ('/dashboard/', '/create_poll/', '/see_answers/'):
            with self.subTest(path=path):
                response = self.client.get(path)
                self.assertRedirects(response, f'/?next={path}', fetch_redirect_response=False)

    def test_unknown_question_redirects_home(self):
        response = self.client.get('/question/not-a-uuid/')
        self.assertRedirects(response, '/', fetch_redirect_response=False)
