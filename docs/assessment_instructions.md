# SKAI Damage Assessment Instructions

Last update: June 1, 2022

Before running these instructions, please make sure that your Google Cloud
project and Linux environment have been set up by following these
[instructions](setup.md).


## Step 1: Set environment variables

Before starting the assessment, please set a few environment variables to streamline running future commands.


```
$ export PROJECT=<your cloud project>
$ export LOCATION=<cloud location, e.g. us-central1>
$ export SERVICE_ACCOUNT=<service account email>
```



## Step 2: Prepare images

Your satellite images must be [Cloud Optimized GeoTIFFs](https://www.cogeo.org/) for SKAI to process them. If you are not sure if your GeoTIFFs are valid Cloud Optimized GeoTIFFs, you can check using this command (make sure the SKAI python virtualenv is activated):


```
$ rio cogeo validate /path/to/images/before.tif

before.tif is a valid cloud optimized GeoTIFF
```


If your images are not COGs, you can use the following command to convert it:


```
$ rio cogeo create /path/to/images/before.tif
```


For more information, see [here](https://cogeotiff.github.io/rio-cogeo/Is_it_a_COG/).

Your satellite images should be uploaded to your Cloud storage bucket so that they can be accessed by the Dataflow preprocessing pipeline. If the images are on your workstation, you can use gsutil to upload them to the bucket.


```
$ gsutil cp /path/to/images/before.tif gs://$BUCKET/images/before.tif
$ gsutil cp /path/to/images/after.tif gs://$BUCKET/images/after.tif
```



## Step 3: Choose an Area of Interest

You need to choose an area of interest (AOI) where SKAI will perform the assessment. This will usually be a polygonal sub-region within the region covered by the before and after images. The AOI should cover the area impacted by the disaster, but not cover areas that you are not interested in analyzing, such as areas clearly not impacted by the disaster.

The AOI should be recorded in a GIS file format, such as [GeoJSON](https://geojson.org/) (preferred) or [Shapefile](https://en.wikipedia.org/wiki/Shapefile). The easiest way to do this is to use a GIS program such as [QGIS](https://www.qgis.org/) that lets you draw a polygon on a map, then save that polygon as a GeoJSON file. This [QGIS tutorial](https://docs.qgis.org/3.22/en/docs/training_manual/create_vector_data/create_new_vector.html) walks through how to do this.


## Step 4: Generate Unlabeled Examples

The next step is to extract examples of buildings in the AOI from the before and after images, and save them in SKAI's training example format. Run the following command to do that. Simultaneously, the command will also create a Cloud example labeling task 


```
$ python generate_examples_main.py \
  --cloud_project=$PROJECT \
  --cloud_region=$LOCATION \
  --before_image_path=gs://$BUCKET/images/before.tif \
  --after_image_path=gs://$BUCKET/images/after.tif \
  --aoi_path=<aoi-path> \
  --output_dir=gs://$BUCKET/examples/test_run \
  --buildings_method=open_street_map \
  --use_dataflow \
  --worker_service_account=$SERVICE_ACCOUNT \
  --create_cloud_labeling_task \
  --cloud_labeler_emails=<labeler-emails>
```


`<aoi-path>` is the path to the AOI file you created in the previous section.

After running this command, you should be able to see a new Dataflow job in the [Cloud console](https://console.cloud.google.com/dataflow/jobs). Clicking on the job will show a real-time monitoring page of the job's progress.

When the Dataflow job finishes, it should have generated a set of sharded TFRecord files containing unlabeled examples of buildings in the output directory you specified.


## Step 5: Create example labeling task

To train a SKAI model, a small number of examples generated in the previous step must be manually labeled. We use the [Vertex AI labeling tool](https://cloud.google.com/vertex-ai/docs/datasets/data-labeling-job) to do this. Run this command to create a labeling task in Vertex AI, and assign the task to a number of human labelers.


```
$ python create_cloud_labeling_task.py \
  --cloud_project=$PROJECT \
  --cloud_location=$LOCATION \
  --import_file=<import file> \
  --dataset_name=<dataset name> \
  --cloud_labeler_emails=<labeler emails>
```



```
<import file> is a file generated in the previous step that contains the paths of image files to use in the labeling task. By default, it should be gs://$BUCKET/examples/test_run/examples/labeling_images/import_file.csv.
```


`<labeler-emails>` is a comma-delimited list of the emails of people who will be labeling example images. They must be Google email accounts, such as GMail or GSuite email accounts.

`<dataset name>` is a name you assign to the dataset to identify it.

An example labeling task will also be created in Vertex AI, and instructions for how to label examples will be sent to all email accounts provided in the `--cloud_labeler_emails` flag.


## Step 6: Label examples

All labelers should follow the [labeling instructions](https://storage.googleapis.com/skai-public/labeling_instructions.pdf) in their emails to manually label a number of building examples. Labeling at least 250 examples each of damaged/destroyed and undamaged buildings should be sufficient. Labeling more examples may improve model accuracy.

**Note:** The labeling task is currently configured with 4 choices for each example - undamaged, possibly\_damaged, damaged\_destroyed, and bad\_example. These text labels are mapped into a binary label, 0 or 1, when generating examples. The mapping is as follows:

*   undamaged, possibly\_damaged, bad\_example --> 0
*   damaged\_destroyed --> 1

Future versions of the SKAI model will have a separate class for bad examples, resulting in 3 classes total.


## Step 7: Merge Labels into Dataset

When a sufficient number of examples are labeled, the labels need to be downloaded and merged into the TFRecords we are training on.

Find the `cloud_dataset_id `of your newly labeled dataset by visiting the
[Vertex AI datasets console](https://console.cloud.google.com/vertex-ai/datasets), and looking at
the "ID" column of your recently created dataset.

![Dataset ID screenshot](https://storage.googleapis.com/skai-public/documentation_images/dataset_id.png "Find dataset ID")


```
$ python create_labeled_dataset.py \
  --cloud_project=$PROJECT \
  --cloud_location=$LOCATION \
  --cloud_dataset_id=<id>
  --cloud_temp_dir=gs://$BUCKET/temp \
  --examples_pattern=gs://$BUCKET/examples/test_run/examples/unlabeled/*.tfrecord \
  --train_output_path=gs://$BUCKET/examples/labeled_train_examples.tfrecord \
  --test_output_path=gs://$BUCKET/examples/labeled_test_examples.tfrecord
```


This will generate two TFRecord files, one containing examples for training and one containing examples for testing. By default, 20% of labeled examples are put into the test set, and the rest go into the training set. This can be changed with the `--test_fraction` flag in the above command.


## Step 8: Train the Model

**Create a Tensorboard resource instance**:


```
$ gcloud ai tensorboards create –display-name <Tensorboard name>

Using endpoint [https://us-central1-aiplatform.googleapis.com/]
Waiting for operation [999391182737489573628]...done.      
Created Vertex AI Tensorboard: projects/123456789012/locations/us-central1/tensorboards/874419473951.
```


The last line of the output is the tensorboard resource name. Pass this value into the flag `--tensorboard_resource_name `flag in the commands below.

**Start the training job:**

Give this experiment a name by passing it through the `--dataset_name `flag and replacing `train_dir_name` in the `--train_dir `flag.


```
$ python launch_vertex_job.py \
--project=$PROJECT \
--location=$LOCATION \
--job_type=train \
--display_name=train_job \
--train_docker_image_uri_path=gcr.io/disaster-assessment/ssl-train-uri \
--tensorboard_resource_name=<tensorboard resource name> \
--service_account=$SERVICE_ACCOUNT \
--dataset_name=dataset_name \
--train_dir=gs://$BUCKET/models/train_dir_name \
--train_label_examples=gs://$BUCKET/examples/labeled_train_examples.tfrecord \
--train_unlabel_examples=gs://$BUCKET/examples/test_run/examples/unlabeled/*.tfrecord \
--test_examples=gs://$BUCKET/examples/labeled_test_examples.tfrecord
```


**Start the eval job:**

This job will continuously evaluate the model on the test dataset and visualize the metrics in the tensorboard.


```
$ python launch_vertex_job.py \
--project=$PROJECT \
--location=$LOCATION \
--job_type=eval \
--display_name=eval_job \
--eval_docker_image_uri_path=gcr.io/disaster-assessment/ssl-eval-uri \
--service_account=$SERVICE_ACCOUNT \
--dataset_name=dataset_name \
--train_dir=gs://$BUCKET/models/train_dir_name \
--train_label_examples=gs://$BUCKET/examples/labeled_train_examples.tfrecord \
--train_unlabel_examples=gs://$BUCKET/examples/test_run/examples/unlabeled/*.tfrecord \
--test_examples=gs://$BUCKET/examples/labeled_test_examples.tfrecord
```

Once you see the evaluation job running, you can monitor the training progress on Tensorboard.

Point your web browser to the [Vertex AI custom training jobs console](https://console.cloud.google.com/vertex-ai/training/custom-jobs). You should see your job listed here. Click on the job, then click the “Open Tensorboard” button at the top.

![Open Tensorboard Screenshot](https://storage.googleapis.com/skai-public/documentation_images/open_tensorboard.png "Open Tensorboard")

**Note:** Tensorboards cost money to maintain. See [this page](https://cloud.google.com/vertex-ai/pricing) under the section "Vertex AI TensorBoard" for the actual cost. To save on Cloud billing, you should remove old Tensorboard instances once the model is trained. Tensorboard instances can be found and deleted on this [Cloud console page](https://console.cloud.google.com/vertex-ai/experiments/tensorboard-instances).


## Step 9: Generate damage assessment file

Run inference to get the model’s predictions on all buildings in the area of interest. 


```
$ python3 launch_vertex_job.py \
  --project=$PROJECT \
  --location=$LOCATION \
  --job_type=eval \
  --display_name=inference \
  --eval_docker_image_uri_path=gcr.io/disaster-assessment/ssl-eval-uri \
  --service_account=$SERVICE_ACCOUNT \
  --dataset_name=dataset_name \
  --train_dir=gs://$BUCKET/models/train_dir_name \
  --test_examples=gs://$BUCKET/examples/labeled_test_examples.tfrecord \
  --inference_mode=True \
  --save_predictions=True
```


**Note:** If you would like to run inference using a specific checkpoint, use the `--eval_ckpt `flag. Example: `--eval_ckpt=gs://$BUCKET/models/train_dir_name/checkpoints/model.ckpt-00851968`. Do NOT include the extension, e.g. ‘.meta’, ‘.data’, or ‘.index’, and only use the prefix.

The predictions will be saved in a directory called `gs://$BUCKET/models/train_dir_name/predictions `as GeoJSON files. The number in each filename refers to the epoch of the checkpoint.


## Feedback

If you have any feedback on these instructions or SKAI in general, we'd love to hear from you. Please reach out to the developers at skai-developers@googlegroups.com, or create an issue in the Github issue tracker.


## Appendix: Build Docker containers for training and eval jobs

In the command for step 8, we used SKAI's default Docker containers for the training and eval jobs. If you make any changes to the training code, such as the model architecture, you must build and push your own Docker containers to the Container Registry, and then launch your training and eval jobs with those containers.

After you have modified the SKAI model source code, use this command to build a local custom container and launch a local training job with it to ensure that it works:


```
$ cd skai/src  # Make sure you're in the SKAI src directory.
$ gcloud beta ai custom-jobs local-run \
--base-image=gcr.io/deeplearning-platform-release/tf2-gpu.2-6 \
--python-module=ssl_train \
--requirements=tensorflow-probability==0.12.2 \
--work-dir=. \
--output-image-uri=gcr.io/$PROJECT/ssl-train-uri \
-- --dataset_name=dataset_name \
--train_dir=gs://$BUCKET/models/train_dir_name \
--train_label_examples=gs://$BUCKET/examples/train_labeled_examples*.tfrecord \
--train_unlabel_examples=gs://$BUCKET/examples/train_unlabeled_examples*.tfrecord \
--test_examples=gs://$BUCKET/examples/test_examples*.tfrecord \
--augmentation_strategy=CTA \
--shuffle_seed=1 \
--num_parallel_calls=2 \
--keep_ckpt=0 \
--train_nimg=0
```


If the previous command doesn't return any errors, use the following command to push the newly built container to the registry:


```
$ docker push gcr.io/$PROJECT/ssl-train-uri
```


Then build the evaluation Docker container, and push it to the registry.


```
$ docker build ./ -f SslEvalDockerfile -t ssl-eval-uri
$ docker tag ssl-eval-uri:latest gcr.io/$PROJECT/ssl-eval-uri
$ docker push gcr.io/$PROJECT/ssl-eval-uri
```


Now you can launch the training and eval jobs on Cloud using the new containers by setting the `--train_docker_image_uri_path` and `--eval_docker_image_uri_path` flags.
