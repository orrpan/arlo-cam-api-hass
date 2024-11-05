ARG BUILD_FROM
FROM $BUILD_FROM

RUN \
  apk add --no-cache \
    python3 \
    py3-pip

COPY requirements.txt /tmp
RUN python3 -m pip install -r /tmp/requirements.txt
RUN rm -f /tmp/requirements.txt

WORKDIR /opt/arlo-cam-api
COPY . ./

EXPOSE 4000/tcp
EXPOSE 4100/tcp
EXPOSE 5000/tcp

# Copy data for add-on
COPY run.sh /
RUN chmod a+x /run.sh

CMD [ "/run.sh" ]