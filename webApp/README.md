# Instructions to set up a web app for SKAI
TODO: A paragraph explaining what it does and the need for it

### Assumptions
The following instructions assume that the user has an existing GCP account. 

### Step 1
Create a new project in GCP and then open the cloud shell
TODO: create a link to get into the cloud shell

### Step 2
Enable the Cloud Build, Cloud Run, Container Registry, and Resource Manager APIs. TODO: add the other services we'll need for the python scripts to run
```
gcloud services enable run.googleapis.com cloudbuild.googleapis.com containerregistry.googleapis.com cloudresourcemanager.googleapis.com
```

### Step 3
To enable the required IAM permissions, please follow [these instructions](https://cloud.google.com/build/docs/deploying-builds/deploy-cloud-run#cloud-run) 
TODO: run IAM permission set up via command line

### Step 4
If you haven't done so already, please clone this repo and cd into it:
```
git clone https://github.com/canlilar/skai
cd skai
```
Next we can deploy the app like this:
```
export PROJECT_ID="$(gcloud config get-value project)"
gcloud builds submit --config=WebAppcloudbuild.yaml
```
You're app is now live! You can find the URL tied to it by navigating to the [Cloud Run service](https://console.cloud.google.com/run?enableapi=true&_ga=2.194155556.883783791.1666026522-1856103480.1665675816) in GCP 
