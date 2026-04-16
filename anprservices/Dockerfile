FROM python:3.11.1
COPY ./ /app
WORKDIR /app
RUN pip install --no-cache-dir -r requirements.txt
RUN CHMOD 444 requirements.txt
EXPOSE 8001
CMD [ "python", "main.py" ]