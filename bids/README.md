This script exports imaging data from the NeuroSpin archive into the 
BIDS format ([Brain Imaging Data Structure](http://bids.neuroimaging.io)).
The BIDS format has been selected because it is simple, easy to share
and supported by lots of software. We are focused on MRI data but other
modalities can be added (diffusion imaging, behavioral, ...). For a full
description, please consult the
[BIDS specifications](http://bids.neuroimaging.io/bids_spec1.0.0.pdf).

This script import data, but also:
* all files such as README, CHANGES, dataset_descrption.json ...
* deface anatomical data if you need
* use the Bids-validator

# Dependencies (can simply pip install packages)

        pip install pydicom --user
        pip install pandas --user
        pip install mne --user
        pip install mne-bids --user
        pip install pydeface --user

# Installation and usage:
## With the installation of the module
You can install the unicog repository and use `neurospin_to_bids.py` from anywhere.
To install the module, please tape:

        cd <path_to_download_to>
        git clone https://github.com/neurospin/unicog.git
        python setup.py install --user

and use as follow:

        neurospin_to_bids.py -h

## Without the installation of the module
If you don't want install the module, you can just use the `neurospin_to_bids.py` script as a python script.
Simply download the unicog repository:

        cd <path_to_download_to>
        git clone https://github.com/neurospin/unicog.git

and use as follow for instance:
                                        
        python <path_to_download_to>/unicog/bids/neurospin_to_bids.py -h


# Preparation of data
## Basic importation
**To import data from NeuroSpin, you have to be connected to the NeuroSpin network.** 
The information about subjects and data to import are stored into a **exp_info** directory. For instance:

        ./exp_info
        ├── participants.tsv


See a small example at [https://github.com/neurospin/unicog/tree/master/bids/test_dataset/](https://github.com/neurospin/unicog/tree/master/bids/test_dataset/)

Also [https://github.com/neurospin/unicog/tree/master/unicogfmri/localizer_pypreprocess/scripts/exp_info](https://github.com/neurospin/unicog/tree/master/unicogfmri/localizer_pypreprocess/scripts/exp_info)


## Advanced importation
The importaiton of events are also possible if the *_events.tsv files are correctly set up.
Here is an example:

        ./exp_info
        ├── participants.tsv
        └── recorded_events
            ├── export_events.py
            ├── sub-01
            │   └── ses-01
            │       └── func
            │           └── sub-01_ses-01_task-loc_events.tsv
            └── sub-02
                └── func
                    └── sub-02_task-loc_events.tsv

# Importation of data
Now we set all files into **exp_info** directory, you can launch the importation:

        cd <path_where_is_exp_info>
        python neurospin_to_bids.py

* The `<path_where_is_exp_info` folder must contain an `exp_info` subfolder containing the participants.tsv file. For more details on the content and structure of these files, read the Additional information section.
* The `neurospin_to_bids.py` script will export files from the NeuroSpin archive based on the information contained in the **exp_info** directory. The script when used as a bash command accept three optional arguments:
    * **-root_path**: specifies the target folder - by default the current directory.
    * **-dataset_name**: the folder name to export the dataset to, by default subfolder `bids_dataset` of the target folder.
    * **-dry-run**: True/False - this mode will test the importaiton without to import data. A list of possible importation and warnings will be displayed.

If instead we were to specify the target folder (the one containing an
`exp_info` subfolder) and a name for the BIDS dataset subfolder, we would
run the command as follows:

        neurospin_to_bids.py -root_path some_path -dataset_name my_dataset

To read the script documentation you can write:

        neurospin_to_bids.py -h

# Additionnal information

## Basic BIDS organization
For anatomical and functional data, the bids nomenclature corresponds to the following organisation of files.

Anatomical:

        sub­-<participant_label>/
            [ses-<session_label>/]
                anat/
                    sub­-<participant_label>[_ses-<session_label>]_T1w.nii[.gz]

Functional:

        sub­-<participant_label>/
            [ses-<session_label>/]
                func/
                    sub­-<participant_label>[_ses-<session_label>]_task-­<task_label>[_run-­<run_label>]_bold.nii[.gz]

As seen by the examples, if you have a session level, a `ses-<session_label>`
subfolder is added under the `sub­-<participant_label>` folder and it would
then be the one to contain the modality folders (here, `anat` or `func`).
Moreover it should also form part of the file names.

The run level `run-<run_label>` is optional if there is only one functional
run for a particular task.

There are plenty more optional fields to include in the file names depending
on your needs. For more details on that please check directly the
[BIDS specifications](http://bids.neuroimaging.io/bids_spec1.0.0.pdf).

Fmap:
This script has an implementation of **case 4: Multiple phase encoded directions** of the BIDS specification.

        sub­-<participant_label>/
            [ses-<session_label>/]
                fmap/
                    sub­<participant_label>[_ses-<session_label>][_acq-<label>]_dir-<label>[_run-<index>]_epi.nii[.gz]
                    sub­<participant_label>[_ses-<session_label>][_acq-<label>]_dir-<label>[_run-<index>]_epi.json
					
					

## Files in the `exp_info` folder specifying the data download

Only one file is mandatory in the `exp_info` directory: `participants.tsv`.
Note that this file is not part of the BIDS standard. It is defined to contain
the minimum information needed to simplify creating a BIDS dataset with the
data from the NeuroSpin server.

### Participants.tsv

Contains information about the participants and their acquisitions.
When there are multiple sessions per subject (with different acquisition
dates), then the _session_label_ column is mandatory. 


        participant_id	NIP		infos_participant		session_label	acq_date	acq_label	location	to_import
        sub-01		tr070015	{"sex":"F", "age":"45"}		01		2010-06-28		trio		[['2','anat','T1w'],['9','func','task-loc_std_run-01_bold'],('10','func','task-loc_std_run-02_bold']]
        sub-02		ap100009	{"sex":"M", "age":"35"}				2010-07-01		trio		[['2','anat','T1w'],['9','func','task-loc_std_bold']]

The _NIP_ column will only be used to identify subjects in the NeuroSpin
database and will not be included in any way on the BIDS dataset to ensure
proper de-identification. Moreover we recommend you to not use the NIP as
the _participant_label_ to avoid the need of future de-identification of
the BIDS dataset before publication.

The _participant_label_ and _session_label_ are taken from this file to
create the folders and file names in the BIDS dataset, every other column
will be added to a new `participants.tsv` file included under the
`bids_dataset` top folder.

#### User case with 2 sessions the same day with the same participant
For instance, if a participant undergoes an examen in the morning and in the afternoon, 
you have to complete the NIP with the number of session. The nip level in Neurospin
is labelled as follow : '<nip>-<exman-number>-<automatic-number>' 
The examen number is automatically incremented for each new examen. Don't mange about
the automatic number. 

Here is an example for the `participants.tsv` file:


        participant_id  NIP             infos_participant               session_label   acq_date	acq_label        location        to_import
        sub-01          tt989898_6405   {"sex":"F", "age":"45"}         01              2010-06-28	      trio            [['2','anat','T1w'],['9','func','task-loc_std_run-01_bold']]
        sub-01          tt989898_6405                                	02 		        2010-06-28	      trio            [['9','func','task-loc_std_bold']]

#### User case for fmap importation (Multiple phase encoded directions)

Here is an example for the `participants.tsv` file:


        participant_id  NIP             infos_participant               session_label   acq_date	acq_label        location        to_import
        sub-01          tt989898_6405   {"sex":"F", "age":"45"}         01              2010-06-28	      prisma            [['24','anat','T1w'],['13','func','task-number_dir-ap_run-01_bold'],['14','func','task-number_dir-ap_run-01_sbref'],['5','fmap','dir-ap_epi',{'intendedFor':'/fmri/sub-301_task-number_dir-ap_run-01_bold'}]]

#### User case for adding a field into the json file
Here we are adding the IndendedFor field into the **fmap/sub-301_dir-ap_epi.json**. This field is not mandatory, but recommended. It seems 
if you use fmriprep, this field is not directly read and fmriprep use the **PhaseEncodingDirection" information which give by the scanner.

		participant_id  NIP     infos_participant       session_label   acq_date        acq_label       location        to_import
		sub-301 jj140402        "{""sex"":""F"", ""age"":""6""}"                2020-01-15          prisma  [['24','anat','T1w'],['13','func','task-number_dir-ap_run-01_bold'),['5','fmap','sub-301_dir-ap_epi',{'IntendedFor':'/func/task-number_dir-ap_run-01_bold'}]]



# Importation of events
The importation of events can not be automatic because very often the events have to extract from log files depending on your stimulation presentation program (expyriment for python).
Here we propose a possible solution, but we are truly free to import yourself into the bids_datset repository the events.
The events for functional runs will be automatically copied in the BIDS dataset if the files are available in a `recorded_events` folder that already respect the bids structure. Which means that files would have the same fields as the bold.nii files in its file name but its final name part would be events.tsv instead, for example:

    <data_root>/exp_info/recorded_events/sub-<sub_label>[/ses-<ses_label>]/func/sub-*_<task>_events.tsv

Here is an example of `sub-*_<task>_events.tsv` following the BIDS standard:

        onset   duration   trial_type
        0.0     1          computation_video
        2.4     1          computation_video
        8.7     1          h_checkerboard
        11.4    1          r_hand_audio
        15.0    1          sentence_audio

the onset, duration and trial_type columns are the only mandatory ones. onset and duration fields should be expressed in second. Other information can be added to events.tsv files such as ​response_time or other arbitrary additional columns respecting subject anonimity. See the [BIDS specification](http://bids.neuroimaging.io/bids_spec1.0.0.pdf).


# Deface
If you want to import data and share them with other laboratories or on an open server, you have to anonymize them. For that, the bids importation remove all fields in the header containing specific
information such as "Patient's name" and the script of importation will propose to deface anatomical data. The pydeface python is used to propose this step.
If you need to deface, ensure that pydeface is installed on your workstation.

Please see [https://github.com/poldracklab/pydeface](https://github.com/poldracklab/pydeface)

# Summary of importation
## Files imported and warnings
A summary will be displayed at the end of importation into the terminal. The summart is also saved into ./report/download_report_*.csv file. This file is not in the bids_dataset repository because it is not part of BIDS.

## BIDS validation
If you are selected the bids validation option, the summary is saved in ./report/report_bids_valisation.txt .

# Notes
* Note 1: if the importation has been interrupted or partially then, then launch again the script. The last partially downloaded data folder will be redownloaded from scratch.
* Note 2: the .tsv extension means "tabulation separated values", so each value must be separated by a tabulation and not commas, spaces or dots. If files in `exp_info` are not tsv, most likely the `neurospin_to_bids.py` script will fail. Please make sure your files comply with your favorite text editor.
