FROM frappe/erpnext:v15.0.0

# Switch to root to modify configurations if necessary
USER root

# Define the custom app to inject into the bench production build
ENV APPS_JSON='[{"url": "https://github.com", "branch": "main"}]'

# Let Frappe internal script fetch and configure your app
USER frappe
RUN export APPS_JSON_BASE64=$(echo ${APPS_JSON} | base64 -w 0) && \
    cd /home/frappe/frappe-bench && \
    bench get-app rhema_daycare
