FROM ghcr.io/painteau/python-ffmpeg-flask-gunicorn:latest
ENV PYTHONUNBUFFERED=1

WORKDIR /app
RUN pip install instaloader

COPY app.py .

USER 1000

CMD ["gunicorn","--bind","0.0.0.0:5633","--access-logfile","-","--error-logfile","-","--timeout","60","app:app"]
