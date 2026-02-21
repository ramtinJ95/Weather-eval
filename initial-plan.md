This is going to be a mono repo for a react frontend, a python backend with
fastapi. its going to be deployed on GCP and we are going to use terraform for
the cloud resources. I reckon we will need a bucket for terraform state. We will
need cloud run to run the docker image. We will need a database because we have
to do some pre calculations of some statistics from an api to speed up the
queries. I think we can start with firebase as our db, should be fine. I want a
single docker image that serves both the frontend and backend since it will just
be a small app. I want ci cd for this project also using github actions. For the
python parts we will use uv, ty and ruff. So the python code should be properly
typed. And i want a linter for the typescript react code also. 

You have access to gcloud cli to explore what is needed. use research subagents to
research anything you are not sure about how to do.

Ask me questions for details that you need to setup a basic hello world version
of this, no need for api connectivity yet. But i would like for you to fetch
something from the database through the backend to show in the frontend so we
can confirm all the parts are wired correctly.
