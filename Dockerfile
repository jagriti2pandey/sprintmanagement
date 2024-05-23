FROM python:3.12 as stage1 
# this is pulling python:3.12 image from docker 
# container ko ek os chahiye hota h to ye python:3.12 is that os image
# why specificly python:3.12? kyuki hume ek lightweight is chahiye or usme sirf required tools chahiye hote h
# to hume faltu dependency nhi chahiye
ENV PYTHONUNBUFFERED 1
# environment variable hum set krte h ek non empty value, 1 mtlb iska koi output na aaye
# output mtlb faltu ke installation message alert na aaye impt msg iske peeche hide ho jate h
RUN python -m pip install hatch

FROM stage1 as stage2
RUN mkdir /app
WORKDIR /app

COPY pyproject.toml /app
COPY config/ /app/config/
COPY README.md /app

COPY . .

FROM stage2 as stage3
CMD ["hatch", "run", "prod:run"]
