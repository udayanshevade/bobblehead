from django.shortcuts import render
from django.http import HttpResponseRedirect
from django.http import Http404
# from django.contrib.auth.forms import UserCreationForm
# from projects.models import Project
from django.contrib.auth import logout
from django.core.urlresolvers import reverse
from .forms import UserProfileForm
from .models import UserProfile

from projects.models import Project, CATEGORY_CHOICES
from submissions.models import Submission

# OpenID imports
from openid.consumer import consumer
# The standard openID formats to ask for user info, sreg is specific to openid provider
from openid.extensions import ax, sreg
from functools import wraps

from config import openid_settings


def is_authenticated():
    """ Decorator to check if user is authenticated """
    def decorator(func):
        @wraps(func)
        def wrapper(request, *args, **kwargs):
            if 'udacity_key' in request.session:
                return func(request, *args, **kwargs)
            else:
                # find the namespace, convert to string
                namespace = func.__module__.split('.')[0]
                function_call = str(namespace+':'+func.__name__)
                redirect = reverse(function_call, args=args, kwargs=kwargs)
                print 'this is the redirect url: ', redirect
                return render(request, 'user_profile/login_projects.html', {'redirect':redirect})
        return wrapper
    return decorator


def logout_projects(request):
    """ Log the user out """
    if request.user and 'udacity_key' not in request.session:
        # If the user was authenticated locally
        logout(request)
    else:
        # If the user was authenticated using Udacity
        try:
            del request.session['udacity_key']
            del request.session['email']
            del request.session['name']
        except KeyError:
            pass
    return HttpResponseRedirect('/projects')


def login_projects(request):
    """ View to log in user. """
    if 'email' in request.session:
        return HttpResponseRedirect('/projects/')
    else:
        return render(request, 'user_profile/login_projects.html')
    return render(request, 'projects/index.html')


@is_authenticated()
def edit(request):
    """ Edit the user's own profile """
    try:
        user_profile = UserProfile.objects.get(email=request.session['email'])
    except UserProfile.DoesNotExist:
        raise Http404("User does not exist/is not signed in")
    if request.method == "POST":
        form = UserProfileForm(request.POST, instance=user_profile)
        # check whether it's valid:
        if form.is_valid():
            m = form.save()
            m.save()
            return HttpResponseRedirect('/user_profile/show/' + str(user_profile.user_key))
    else:
        return render(request, 'user_profile/edit_profile.html',
                      {'form': UserProfileForm(instance=user_profile), 'user_profile': user_profile, 'nanodegree_choices':UserProfile.NANODEGREE_CHOICES},)


@is_authenticated()
def show(request, user_key):
    """ Show user's profile, and the project's they have created. """
    try:
        user_profile = UserProfile.objects.get(user_key=user_key)
        projects_list = Project.objects.filter(user=user_profile)
        # Return all submissions that the user has made.
        submissions = Submission.objects.filter(members__in=[user_profile])
    except UserProfile.DoesNotExist:
        raise Http404("User doesnt exist")
    return render(request,
                  'user_profile/show_profile.html',
                  {'user_profile': user_profile,
                   'projects': projects_list,
                   'submissions_list': submissions,
                   'current_user': request.session['email']}
                  )


@is_authenticated()
def view(request, user_key):
    """ View user's profile, and the project's they have created. """
    try:
        user_profile = UserProfile.objects.get(user_key=user_key)
        projects_list = Project.objects.filter(user=user_profile)
        # Return all submissions that the user has made.
        submissions = Submission.objects.filter(members__in=[user_profile])
    except UserProfile.DoesNotExist:
        raise Http404("User doesnt exist")
    return render(request, 'user_profile/view_profile.html', {'user_profile': user_profile, 'projects': projects_list, 'submissions_list': submissions})


def login_udacity(request):
    """ Authenticate with Udacity using OpenID """
    if not hasattr(login_udacity, 'redirect_on_return'):
        login_udacity.redirect_on_return = '/projects/'
    if request.method == "POST":
        login_udacity.redirect_on_return = request.POST['redirect']
        cons_obj = consumer.Consumer(request.session, None)
        openid_url = "https://www.udacity.com/openid"
        auth_request = cons_obj.begin(openid_url)

        # extending the reuqest object
        sreg_request = sreg.SRegRequest(
            required=['fullname', 'email', 'nickname'],
        )
        auth_request.addExtension(sreg_request)

        # To request for getting user_id @ udacity
        ax_request = ax.FetchRequest()
        # The url is associated with the user_id format at udacity
        ax_request.add(ax.AttrInfo('http://openid.net/schema/person/guid',
                                   required=True,))

        auth_request.addExtension(ax_request)

        realm_url = openid_settings.REALM_URL
        return_url = openid_settings.RETURN_URL

        udacity_url = auth_request.redirectURL(realm_url, return_url)
        return HttpResponseRedirect(udacity_url)
    elif request.method == "GET":
        """ Callback function for authentication with Udacity. """
        cons_obj = consumer.Consumer(request.session, None)
        path = openid_settings.RETURN_URL
        the_response = cons_obj.complete(request.GET, path)
        if the_response.status == consumer.SUCCESS:
            # Gather Info from Udacity
            sreg_response = sreg.SRegResponse.fromSuccessResponse(the_response)
            if sreg_response:
                sreg_items = {
                    'email': sreg_response.get('email'),
                    'name': sreg_response.get('nickname'),
                }
            ax_response = ax.FetchResponse.fromSuccessResponse(the_response)
            if ax_response:
                ax_items = {
                    'udacity_key': ax_response.get('http://openid.net/schema/person/guid')[0],
                }
            # Store items returned from Udacity in the session object
            for key in sreg_items:
                request.session[key] = sreg_items[key]
            for key in ax_items:
                request.session[key] = ax_items[key]

            if not UserProfile.objects.filter(udacity_key=request.session['udacity_key']).exists():
                user_profile = UserProfile(email=request.session['email'],
                                           nickname=request.session['name'],
                                           udacity_key=request.session['udacity_key'])

                user_profile.save()
        else:
            print "Nope"
        print ">>>>>>> we will redirect to - ", login_udacity.redirect_on_return
        return HttpResponseRedirect(login_udacity.redirect_on_return)
