# Use the pre-built Selenium image with Chrome
FROM selenium/standalone-chrome:latest

# Install packageas with root priviliges
USER root
RUN apt-get update && \
    apt-get install -y python3 python3-pip python3-venv

# Add a user for running stuff and switch to that user
USER seluser

# Copy the application code into the container and add the working directory
COPY --chown=seluser:seluser . /home/seluser/app
WORKDIR /home/seluser/app

# Install Python dependencies
RUN python3 -m venv .venv
RUN .venv/bin/pip install -r requirements.txt
RUN .venv/bin/pip install --upgrade chromedriver-autoinstaller


# Ensure the virtual environment is in the PATH
ENV PATH="/home/seluser/app/.venv/bin:$PATH"
