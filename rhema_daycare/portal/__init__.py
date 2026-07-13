# The real has_website_permission implementation lives in
# rhema_daycare.portal.permissions (registered in hooks.py's
# has_website_permission dict). This file previously carried a second,
# weaker copy — it didn't check ptype, didn't require status=Active, and
# ignored Additional Guardians — that was never wired up but was a footgun
# for anyone who later imported from here instead of portal.permissions.