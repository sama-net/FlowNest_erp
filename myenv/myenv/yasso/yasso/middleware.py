from django.contrib.sessions.middleware import SessionMiddleware
from django.conf import settings

class DynamicSessionMiddleware(SessionMiddleware):
    """
    A brilliant middleware to allow true Multi-sessions in the same browser (Tabs).
    It intercepts the session cookie and dynamically suffixes it based on the '?workspace='
    parameter or the 'active_workspace' cookie.
    """
    def process_request(self, request):
        workspace = request.GET.get('workspace') or request.COOKIES.get('active_workspace', 'default')
        cookie_name = f"sessionid_{workspace}" if workspace != 'default' else settings.SESSION_COOKIE_NAME
        
        session_key = request.COOKIES.get(cookie_name)
        request.session = self.SessionStore(session_key)
        request.active_workspace = workspace

    def process_response(self, request, response):
        # Let Django's default SessionMiddleware do its thing first
        response = super().process_response(request, response)
        
        workspace = getattr(request, 'active_workspace', 'default')
        if workspace != 'default':
            cookie_name = f"sessionid_{workspace}"
            
            # Rename the set-cookie header from 'sessionid' to 'sessionid_X'
            if settings.SESSION_COOKIE_NAME in response.cookies:
                cookie = response.cookies[settings.SESSION_COOKIE_NAME]
                response.set_cookie(
                    cookie_name,
                    cookie.value,
                    max_age=cookie.get('max-age'),
                    expires=cookie.get('expires'),
                    domain=cookie.get('domain'),
                    path=cookie.get('path'),
                    secure=cookie.get('secure') or False,
                    httponly=cookie.get('httponly') or False,
                    samesite=cookie.get('samesite'),
                )
                del response.cookies[settings.SESSION_COOKIE_NAME]
                
            response.set_cookie('active_workspace', workspace)
        return response
