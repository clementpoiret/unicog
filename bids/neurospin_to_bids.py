import os
import pandas as pd
from ast import literal_eval
import json
import glob as glob
import json
import shutil
import subprocess
from pathlib import Path
from pkg_resources import resource_filename, Requirement  
import yaml

from bids_validator import BIDSValidator
import pydeface.utils as pdu
import mne
from mne_bids import write_raw_bids, make_dataset_description
import pydicom
from itertools import combinations
import time
import argparse
import re


NEUROSPIN_DATABASES = {
    'prisma': '/neurospin/acquisition/database/Prisma_fit',
    'trio': '/neurospin/acquisition/database/TrioTim',
    'meg' : '/neurospin/acquisition/neuromag/data',
}



def yes_no(question_to_be_answered):
    while True:
        choice = input(question_to_be_answered).lower()
        if choice[:1] == 'y': 
            return True
        elif choice[:1] == 'n':
            return False
        else:
            print("Please respond with 'y/n'\n")

def file_manager_default_file(main_path, filter_list, file_tag,
                              file_type='*', allow_other_fields=True):
    """Path to the most specific file with respect to optional filters.

    Each filter is a list [key, value]. Like [sub, 01] or [ses, 02].

    Following BIDS standard files can be of the form
    [key-value_]...[key-value_]file_tag.file_type.
    """
    filters = []
    for n in list(reversed(range(1, len(filter_list) + 1))):
        filters += combinations(filter_list, n)
    filters += [[]]
    for filt in filters:
        found = get_bids_files(main_path,
                               sub_folder=False, file_type=file_type,
                               file_tag=file_tag, filters=filt,
                               allow_other_fields=allow_other_fields)
        if found:
            return found[0]
    return None


def file_reference(img_path):
    reference = {}
    reference['file_path'] = img_path
    reference['file_basename'] = os.path.basename(img_path)
    parts = reference['file_basename'].split('_')
    tag, typ = parts[-1].split('.', 1)
    reference['file_tag'] = tag
    reference['file_type'] = typ
    reference['file_fields'] = ''
    reference['fields_ordered'] = []
    for part in parts[:-1]:
        reference['file_fields'] += part + '_'
        field, value = part.split('-')
        reference['fields_ordered'].append(field)
        reference[field] = value
    return reference


def get_bids_files(main_path, file_tag='*', file_type='*', sub_id='*',
                   file_folder='*', filters=[], ref=False, sub_folder=True,
                   allow_other_fields=True):
    """Return files following bids spec

    Filters are of the form (key, value). Only one filter per key allowed.
    A file for which a filter do not apply will be discarded.
    """
    if sub_folder:
        files = os.path.join(main_path, 'sub-*', 'ses-*')
        if glob.glob(files):
            files = os.path.join(main_path, 'sub-%s' % sub_id, 'ses-*',
                                 file_folder, 'sub-%s*_%s.%s' %
                                 (sub_id, file_tag, file_type))
        else:
            files = os.path.join(main_path, 'sub-%s' % sub_id, file_folder,
                                 'sub-%s*_%s.%s' %
                                 (sub_id, file_tag, file_type))
    else:
        files = os.path.join(main_path, '*%s.%s' % (file_tag, file_type))

    files = glob.glob(files)
    files.sort()
    if filters:
        if not allow_other_fields:
            files = [file_ for file_ in files if
                     len(os.path.basename(file_).split('_')) <=
                     len(filters) + 1]
        files = [file_reference(file_) for file_ in files]
        for key, value in filters:
            files = [file_ for file_ in files if (key in file_ and
                                                  file_[key] == value)]
    else:
        files = [file_reference(file_) for file_ in files]

    if ref:
        return files
    else:
        return [ref_file['file_path'] for ref_file in files]


def bids_copy_events(behav_path='exp_info/recorded_events', data_root_path='',
                     dataset_name=None):
    data_path = get_bids_default_path(data_root_path, dataset_name)
    print(os.path.join(data_root_path, behav_path, 'sub-*', 'ses-*'))
    if glob.glob(os.path.join(data_root_path, behav_path, 'sub-*', 'ses-*')):
        sub_folders = glob.glob(os.path.join(behav_path, 'sub-*', 'ses-*',
                                             'func'))
    else:
        print(os.path.join(data_root_path, behav_path,'sub-*', 'func'))
        sub_folders = glob.glob(os.path.join(data_root_path, behav_path,
                                             'sub-*', 'func'))

    # raise warning if no folder is found in recorded events
    if not sub_folders:
        print('****  BIDS IMPORTATION WARMING: NO EVENTS FILE')
    else:
        for sub_folder in sub_folders:
            #file_path = sub_folder.replace(behav_path + '/', '')
            file_path = sub_folder
            for file_name in os.listdir(os.path.join(sub_folder)):

#                dest_directory = os.path.join(data_path, file_path)
#                if not os.path.exists(dest_directory):
#                    os.makedirs(dest_directory)

                file_ext = []
                last = ''
                root, last = os.path.split(sub_folder)
                while last != 'recorded_events':
                    if last == '':
                        break
                    file_ext.append(last)
                    sub_folder = root
                    root, last = os.path.split(sub_folder)

                list_tmp = []
                elements_path = [[item, '/'] for item in reversed(file_ext)]
                elements_path = [(list_tmp.append(item[0]),
                                  list_tmp.append(item[1]))
                                 for item in elements_path]
                ext = ''.join(list_tmp)
                shutil.copyfile(os.path.join(file_path, file_name),
                                os.path.join(data_path, ext, file_name))


def get_bids_path(data_root_path='', subject_id='01', folder='',
                  session_id=None):
    if session_id is None:
        session_id = ''
    else:
        session_id = 'ses-' + session_id
    return os.path.join(data_root_path, 'sub-' + subject_id,
                        session_id, folder)


def get_bids_file_descriptor(subject_id, task_id=None, session_id=None,
                             acq_label=None, rec_id=None, run_id=None,
                             file_tag=None, file_type=None):
    """ Creates a filename descriptor following BIDS.

    subject_id refers to the subject label
    task_id refers to the task label
    run_id refers to run index
    acq_label refers to acquisition parameters as a label
    rec_id refers to reconstruction parameters as a label
    """
    if 'sub-' or 'sub' in subject_id:
        descriptor = subject_id
    else:
        descriptor = 'sub-{0}'.format(subject_id)
    if session_id is not None:
        descriptor += '_ses-{0}'.format(session_id)
    if task_id is not None:
        descriptor += '_task-{0}'.format(task_id)
    if acq_label is not None:
        descriptor += '_acq-{0}'.format(acq_label)
    if rec_id is not None:
        descriptor += '_rec-{0}'.format(rec_id)
    if run_id is not None:
        descriptor += '_run-{0}'.format(run_id)
    if file_tag is not None and file_type is not None:
        descriptor += '_{0}.{1}'.format(file_tag, file_type)
    return descriptor


def get_bids_default_path(data_root_path='', dataset_name=None):
    """Default experiment raw dataset folder name"""
    if dataset_name is None:
        dataset_name = 'bids_dataset'
    return os.path.join(data_root_path, dataset_name)


def bids_init_dataset(data_root_path='', dataset_name=None,
                      dataset_description=dict(), readme='', changes=''):
    """Create directories and files missing to follow bids.

    Files and folders already created will be left untouched.
    This is an utility to initialize all files that should be present
    according to the standard. Particularly those that should be filled
    manually like participants.tsv and README files.

    participants.tsv columns can be extended as desired, the first column
    is mandatory by the standard, while the acq_date and NIP columns are only
    relevant as NeuroSpin/Unicog scanning reference and will be useful for
    automatic download of acquisitions respecting bids conventions.

    README is quite free as a file

    CHANGES follow CPAN standards

    Mandatory fields for dataset description saved by default are:
    Name: dataset_name
    BidsVersion: 1.0.0
    """
    # Check dataset repository
    dataset_name_path = get_bids_default_path(data_root_path, dataset_name)
    if not os.path.exists(dataset_name_path):
        os.makedirs(dataset_name_path)
        
    # Check dataset_description.json file
#    dataset_description_file = os.path.join(get_bids_default_path(data_root_path, dataset_name),
#                     'dataset_description.json')
#    if not os.path.isfile(dataset_description_file):
#        f = open(dataset_description_file, 'w')
#        dataset_description.update({'Name': dataset_name,
#                                    'BIDSVersion': '1.1.0'})
#        json.dump(dataset_description, f)
        
    # Check README file
    data_description_path = get_bids_default_path(data_root_path, dataset_name)
    data_descrip = yes_no('\nDo you want to create and complete the dataset_description.json ? (y/n)')
    if data_descrip :
        print('\nIf you do not know all information: pass and edit the file later.')
        name = input("\nTape the name of this BIDS dataset: ").lower()
        authors = input("\nA list of authors like [‘a’, ‘b’, ‘c’]: ").lower()
        acknowledgements = input("\nA list of acknowledgements like [‘a’, ‘b’, ‘c’]: ").lower()
        how_to_acknowledge = input("\nEither a str describing how to acknowledge this dataset OR a list of publications that should be cited : ")
        funding = input('\nList of sources of funding (e.g., grant numbers). Must be a list of strings or a single comma separated string like [‘a’, ‘b’, ‘c’] : ')
        references_and_links = input("\nList of references to publication that contain information on the dataset, or links. Must be a list of strings or a single comma separated string like [‘a’, ‘b’, ‘c’] :")
        doi = input('\nThe DOI for the dataset : ')
        make_dataset_description(data_description_path, name=name, data_license=None, authors=authors, acknowledgements=acknowledgements, how_to_acknowledge=how_to_acknowledge, funding=funding, references_and_links=references_and_links, doi=doi, verbose=False)
    else:
        print("You may create later the README file. For this use mne_bids.make_dataset_description function")
    
    # Check CHANGES file / text file CPAN convention
    changes = yes_no('\nDo you want to create/complete the CHANGES file ? (y/n)')
    if changes:
        changes_file = os.path.join(get_bids_default_path(data_root_path, 
                                                          dataset_name),
                                                          'CHANGES')
        f = open(changes_file , 'a')
        #f.write(changes)
        f.close()
        
    # Check README file / text file
    readme = yes_no('\nDo you want to create/complete the README file ? (y/n)')
    if readme:
        readme_file = os.path.join(get_bids_default_path(data_root_path, 
                                                          dataset_name),
                                                          'README')
        f = open(readme_file , 'a')
        #f.write(readme)
        f.close()

def bids_acquisition_download(data_root_path='', dataset_name=None,
                              force_download=False,
                              behav_path='exp_info/recorded_events',
                              copy_events='n',
                              deface=False,
                              test_paths=False):
#def bids_acquisition_download(data_root_path='', dataset_name=None,
#                              download_database='prisma',
#                              force_download=False,
#                              behav_path='exp_info/recorded_events',
#                              test_paths=False):
    """Automatically download files from neurospin server to a BIDS dataset.

    Download-database is based on NeuroSpin server conventions.
    Options are 'prisma', 'trio' and custom path.
    Prisma db_path = '/neurospin/acquisition/database/Prisma_fit'
    Trio db_path = '/neurospin/acquisition/database/TrioTim'

    The bids dataset is created if necessary before download with some
    empy mandatory files to be filled like README in case they dont exist.

    The download depends on the file '[sub-*_][ses-*_]download.csv' contained
    in the folder 'exp_info'.

    NIP and acq date of the subjects will be taken automatically from
    exp_info/participants.tsv file that follows bids standard. The file will
    be copied in the dataset folder without the NIP column for privacy.

    Posible exceptions
    1) exp_info directory not found
    2) participants.tsv not found
    3) download files not found
    4) Acquisition directory in neurospin server not found
    5) There is more than one acquisition directory (Have to ask manip for
    extra digits for NIP, the NIP then would look like xxxxxxxx-ssss)
    6) Event file corresponding to downloaded bold.nii not found
    """

    # Check paths and files
    
    #Path exp_info where the participants.tsv file will be found
    exp_info_path = os.path.join(data_root_path, 'exp_info')
    if not os.path.exists(exp_info_path):
        raise Exception('exp_info directory not found')
    if not os.path.isfile(os.path.join(exp_info_path, 'participants.tsv')):
        raise Exception('exp_info/participants.tsv not found')

    # Determine target path 
    target_root_path = get_bids_default_path(data_root_path, dataset_name)

#    # Determine path to files in NeuroSpin server
#    if download_database in NEUROSPIN_DATABASES:
#        db_path = NEUROSPIN_DATABASES[download_database]
#    else:
#        db_path = download_database

    # Create dataset directories and files if necessary
    bids_init_dataset(data_root_path, dataset_name)

    #READ THE PARTICIPANTS.TSV FILE
    # Get info of subjects/sessions to download
    pop = pd.read_csv(os.path.join(exp_info_path, 'participants.tsv'),
                      dtype=str, sep='\t', index_col=False)

    # Manage the report and download information
    download_report = ('download_report_' +
                       time.strftime("%d-%b-%Y-%H:%M:%S", time.gmtime()) +
                       '.csv')
    report_path = os.path.join(data_root_path, 'report')
    if not os.path.exists(report_path):
        os.makedirs(report_path)
    download_report = open(os.path.join(report_path,
                                        download_report), 'w')
    report_line = '%s,%s,%s\n' % ('subject_id', 'session_id', 'download_file')
    download_report.write(report_line)
    
    # Create a dataFrame to store participant information
    df_participant = pd.DataFrame()    
    
    # List for the bacth file for dc2nii_batch command
    infiles_dcm2nii = []
    
    # List fr data to deface
    files_for_pydeface = []
    
    #Dict of descriptors to be added
    dict_descriptors = {}
    
    # Download command for each subject/session
    # (following neurospin server conventions)
    # one line has the following information
    # participant_id / NIP / infos_participant / session_label / acq_date / location / to_import

    for row_idx, subject_info in pop.iterrows():
                
        # Fill the partcipant information for the participants.tsv
        info_participant = json.loads(subject_info['infos_participant'])  
        info_participant['participant_id']=subject_info['participant_id'] 
        print(info_participant)
        df_participant = df_participant.append(info_participant, ignore_index=True)
        
        # Determine path to files in NeuroSpin server  
        download_database = subject_info['location']        
        if download_database in NEUROSPIN_DATABASES:
            db_path = NEUROSPIN_DATABASES[download_database]
        else:
            db_path = download_database         
        
        #create a dico to store json info
        dico_json = {}
        
        #the row_idx for giving either participant_label or participant_id
        subject_id = subject_info[0]
        
        #Name + creation for the sub_path: target_root_path + subject_id + ses_path
        if 'session_label' in subject_info.index:
            if subject_info['session_label'] is not pd.np.nan:
                session_id = subject_info['session_label']
            else:
                session_id = None
        if session_id is None:
            ses_path = ''
        else:
            ses_path = 'ses-' + session_id     
        try:
            int(subject_id)
            subject_id = 'sub-{0}'.format(subject_id)
        except:
            if ('sub-') in subject_id:
                subject_id = subject_id
            else:
                subject_id = subject_id
                print('****  BIDS IMPORTATION WARMING: SUBJECT ID PROBABLY '
                      'NOT CONFORM')
        sub_path = os.path.join(target_root_path, subject_id,
                                ses_path)
        if not os.path.exists(sub_path):
            os.makedirs(sub_path)
            
        # Avoid redownloading subjects/sessions
        if not force_download:
            check_file = os.path.join(sub_path, 'downloaded')
            if os.path.isfile(check_file):
                continue


        # DATE has to be transformed from BIDS to NeuroSpin server standard
        # NeuroSpin standard is yyyymmdd -> Bids standard is YYYY-MM-DD
        acq_date = subject_info['acq_date'].replace('-', '').replace('\n', '')
        nip = subject_info['NIP']
        #print(os.path.join(db_path, str(acq_date), str(nip) + '-*'))

#        #Mange the optional filters
#        optional_filters = [('sub', subject_id)]
#        if session_id is not None:
#            optional_filters += [('ses', session_id)]

        # Get appropriate download file. As specific as possible
#        specs_path = file_manager_default_file(exp_info_path,
#                                               optional_filters, 'download',
#                                               file_type='tsv',
#                                               allow_other_fields=False)
#        report_line = '%s,%s,%s\n' % (subject_id, session_id, specs_path)
#        download_report.write(report_line)

        #specs = pd.read_csv(specs_path, dtype=str, sep='\t', index_col=False)
        
        #Retrieve list of list for seqs to import
        #One tuple is configured as :(file_to_import;acq_folder;acq_name) 
        #value[0] : num of seq
        #value[1] : modality
        #value[2] : part of ht file_name
        
        seqs_to_retrieve = literal_eval(subject_info['to_import'])

        # clean directories, in case a previous download failed
        #for ridx, row in specs.iterrows():
        for value in seqs_to_retrieve:
#            toclean = os.path.join(sub_path, row['acq_folder'])
            toclean = os.path.join(sub_path, value[1])
        if os.path.exists(toclean):
            shutil.rmtree(toclean)

        # download data, store information in batch files for anat/fmri
        # ---  for meg data
        #for ridx, row in specs.iterrows():
        for value in seqs_to_retrieve:
            def get_value(key, text):
                m = re.search(key + '-(.+?)_', text)
                if m:
                    return m.group(1)
                else:
                    return None

#            dico_json['TaskName'] = row['task_name']
#            run_task = get_value('task', row['acq_name'])
#            run_id = get_value('run', row['acq_name'])
#           dico_json['TaskName'] = value[2]
            run_task = get_value('task', value[2])
            run_id = get_value('run', value[2])            
            run_session = session_id
            
            #tag = row['acq_name'].split('_')[-1]
            tag = value[2].split('_')[-1]
            print ("tag", tag)
            #target_path = os.path.join(sub_path, row['acq_folder'])
            #target_path = sub_path(target_root_path+subject_id+ses_path)+modality
            #target_path = /volatile/BIDS/test_demo/bids_dataset/sub-02/func
            target_path = os.path.join(sub_path, value[1])
            
            if value[1] == 'meg':
                # Create subject path if necessary
                meg_path = os.path.join(sub_path, 'meg')
                if not os.path.exists(meg_path):
                    os.makedirs(meg_path)
                    
                # Create the sub-emptyroom
                #sub-emptyroom_path = os.path.join(data_root_path, 'sub_emptyroom')
#                if not os.path.exists(sub-emptyroom_path):
#                    os.makedirs(sub-emptyroom_path)
                
                meg_file = os.path.join(db_path, nip, acq_date, value[0])
                print(meg_file)
                filename = get_bids_file_descriptor(subject_id, task_id=run_task,
                                                    run_id=run_id,
                                                    session_id=run_session,
                                                    file_tag=tag,
                                                    file_type='tif')
                #output_path = os.path.join(target_path, filename)
#                print(output_path)
#                shutil.copyfile(meg_file, output_path)
                raw = mne.io.read_raw_fif(meg_file, allow_maxshield=True)

                write_raw_bids(raw, filename, target_path,
                                overwrite=True)
                # add event 
                # create json file
                
                
                #copy the subject emptyroom
                
                
                # changer download de niveau 
                
            elif (value[1] == 'anat') or (value[1] == 'func'):
                #nip_dirs : directory of the subject in neurospinacquisition
                nip_dirs = glob.glob(os.path.join(db_path, str(acq_date), str(nip) + '-*'))
                #print('\n\nSTART FOR :', subject_id)
                #print(os.path.join(db_path, str(acq_date), str(nip) + '-*'), '\n')
                
                if len(nip_dirs) < 1:
                    raise Exception('****  BIDS IMPORTATION WARMING: \
                            No directory found for given NIP %s SESSION %s' %
                            (nip, session_id))
                elif len(nip_dirs) > 1:
                    raise Exception('****  BIDS IMPORTATION WARMING: \
                            Multiple path for given NIP %s SESSION %s - please \
                            mention the session of the subject for this date, \
                            2 sessions for the same subject the same day are \
                            possibble' %
                            (nip, session_id))
                
                #dicom_path = os.path.join(target_path, 'dicom')
    
                #row[0], either acq_number or acq_id
                #run_path = glob.glob(os.path.join(nip_dirs[0], '{0:06d}_*'.
                #                                  format(int(row[0]))))
                run_path = glob.glob(os.path.join(nip_dirs[0], '{0:06d}_*'.
                                                  format(int(value[0]))))[0]
#                if run_path:
#                    print("----------- FILE IN PROCESS : ", run_path)
#                    shutil.copytree(run_path[0], dicom_path)
#                else:
#                    raise Exception('****  BIDS IMPORTATION WARMING: '
#                                    'DICOM FILES NOT FOUNDS FOR RUN %s'
#                                    ' TASK %s SES %s SUB %s TAG %s' %
#                                    (run_id, run_task, run_session,
#                                     subject_id, tag))
#    
    #            subprocess.call("dcm2nii -g n -d n -e n -p n " + dicom_path,
    #                            shell=True)
    
                # Switch to dcm2niix / ba option for anonymise BIDS / -z to compress  
#                subprocess.call(("dcm2niix -ba y -z n -o {output_path} \
#                                  {data_path}".format(output_path=dicom_path, 
#                                  data_path=dicom_path)),
#                                  shell=True)
    
                # Expecting page 10 bids specification file name
                filename = get_bids_file_descriptor(subject_id, task_id=run_task,
                                                    run_id=run_id,
                                                    session_id=run_session,
                                                    file_tag=tag,
                                                    file_type='nii')
                
 
#                nii_file = glob.glob(os.path.join(dicom_path, '*.nii'))[0]
#                                
                if value[1] == 'anat' and deface :
                    
                    print("Deface with pydeface")
                    
#                
#                    template = resource_filename(Requirement.parse("unicog"),
#                                                 "bids/template_deface/mean_reg2mean.nii.gz")
#                    
#                    facemask = resource_filename(Requirement.parse("unicog"),
#                                                 "bids/template_deface/facemask.nii.gz")
                      
                    files_for_pydeface.append(os.path.join(target_path, filename))
#                    pdu.deface_image(infile=nii_file, 
#                                         outfile=nii_file, 
#                                         facemask=facemask,
#                                         template=template,
#                                         force=True)  
                    
                    ##pydeface Dicom_mprage_sag_T1_160sl_20191016130146_2.nii --outfile deface_pydeface.nii
    
    
#                shutil.copyfile(nii_file, os.path.join(target_path, filename))
#                if glob.glob(os.path.join(dicom_path, '*.json')):
#                    shutil.copyfile(glob.glob(
#                                    os.path.join(dicom_path, '*.json'))[0],
#                                    os.path.join(filename_json))
                    

                
    
                # Will be done with dcm2niix in the future (get all header fields)
                # Copy slice_times from dicom reference file
    #            if 'bold' in row['acq_name']:
    #                dicom_ref = sorted(glob.glob(os.path.join(dicom_path,
    #                                   '*.dcm')))[4]
    #                json_ref = open(os.path.join(target_path, filename[:-3] +
    #                                'json'), 'a')
    #                try:
    #                    slice_times = pydicom.read_file(dicom_ref)[0x19, 0x1029].value
    #                    if (max(slice_times) > 1000):
    #                        print('****  BIDS IMPORTATION WARMING: '
    #                              'SLICE TIMING SEEM TO BE IN MS, '
    #                              'CONVERSION IN Seconds IS DONE')
    #                        print(slice_times)
    #                        slice_times = [round((v*10**-3), 4)
    #                                       for v in slice_times]
    #                    dico_json['SliceTiming'] = slice_times
    #                    #json.dump({'SliceTiming': slice_times}, json_ref)
    #                except:
    #                    print('****  BIDS IMPORTATION WARMING: '
    #                          'No value for slicee timing, please '
    #                          'add information manually in json file.')
    #                TR = pydicom.read_file(dicom_ref).RepetitionTime
    #                if (TR > 10):
    #                        print('****  BIDS IMPORTATION WARMING: '
    #                              'REPETITION TIME SEEM TO BE IN MS, '
    #                              'CONVERSION IN Seconds IS DONE')
    #                        TR = round((TR * 10**-3), 4)
    #                dico_json['RepetitionTime'] = TR
    #                #json.dump({'RepetitionTime': TR}, json_ref)
    #                json.dump(dico_json, json_ref)
    #                json_ref.close()
                # remove temporary dicom folder
      #          shutil.rmtree(dicom_path)
                
#                file_to_convert = {'in_dir': sub_path, 
#                                   'out_dir': target_root_path, 
#                                   'filename': filename}

                file_to_convert = {'in_dir': run_path, 
                                   'out_dir': target_path, 
                                   'filename': os.path.splitext(filename)[0]}

                if not os.path.exists(target_path):
                    os.makedirs(target_path)
                
                infiles_dcm2nii.append(file_to_convert)
                #print(infiles_dcm2nii)
                
                # Add descriptor into the json file
                if run_task:
                    filename_json = os.path.join(target_path, filename[:-3] + 'json')
                    dict_descriptors.update({filename_json: {'TaskName':run_task}})
                
        #Importation and conversion of dicom files        
        dcm2nii_batch = dict(Options=dict(isGz='false', 
                                          isFlipY='false', 
                                          isVerbose='false', 
                                          isCreateBIDS='true',
                                          isOnlySingleFile='false'), 
                                          Files=infiles_dcm2nii)
                        
#        dcm2nii_batch_file = os.path.join(exp_info_path, 'batch_dcm2nii.yaml')
#        #dcm2nii_batch_file = "/neurospin/unicog/protocols/IRMf/Unicogfmri/BIDS/test_demo/exp_info/batch_dcm2nii.yaml"
#        with open(dcm2nii_batch_file, 'w') as f:
#            data = yaml.dump(dcm2nii_batch, f)
#            
#        cmd = "dcm2niibatch %s"%(dcm2nii_batch_file)
#        subprocess.call(cmd, shell=True)   
        
        #add the downloaded files 
            
        done_file = open(os.path.join(sub_path, 'downloaded'), 'w')
        done_file.close()
    download_report.close()
    
    dcm2nii_batch_file = os.path.join(exp_info_path, 'batch_dcm2nii.yaml')
    #dcm2nii_batch_file = "/neurospin/unicog/protocols/IRMf/Unicogfmri/BIDS/test_demo/exp_info/batch_dcm2nii.yaml"
    with open(dcm2nii_batch_file, 'w') as f:
        data = yaml.dump(dcm2nii_batch, f)
        
    cmd = "dcm2niibatch %s"%(dcm2nii_batch_file)
    subprocess.call(cmd, shell=True)  
    
    #Data to deface
    print(files_for_pydeface)
    if files_for_pydeface :
        template = resource_filename(Requirement.parse("unicog"),
                        "bids/template_deface//mean_reg2mean.nii.gz")
        facemask = resource_filename(Requirement.parse("unicog"),
                        "bids/template_deface/facemask.nii.gz")
        
        os.environ['FSLDIR'] = "/i2bm/local/fsl/bin/"
        os.environ['FSLOUTPUTTYPE'] = "NIFTI_PAIR"
        os.environ['PATH'] = os.environ['FSLDIR']+":"+os.environ['PATH']
        
        print(os.environ['FSLDIR']) 
        print(os.environ['FSLOUTPUTTYPE']) 
        print(os.environ['PATH'])
        
        for file_to_deface in files_for_pydeface:
            print("Deface with pydeface") 
            pdu.deface_image(infile=file_to_deface, 
                                 outfile=file_to_deface, 
                                 facemask=facemask,
                                 template=template,
                                 force=True)  


    # Create participants.tsv in dataset folder (take out NIP column)
    participants_path = os.path.join(target_root_path, 'participants.tsv')
#    pop = pop.drop('acq_date', 1)
#    pop.drop('NIP', 1).to_csv(participants_path, sep='\t', index=False)
    df_participant.to_csv(participants_path, sep='\t', index=False)

    if dict_descriptors:
        print(dict_descriptors)
        # Adding a new key value pair in a json file such as taskname
        for k, v in dict_descriptors.items():
            with open(k, 'r+') as json_file:
                for key, val in v.items() :
                    temp_json = json.load(json_file)
                    temp_json[key] = val
                    json_file.seek(0)
                    json.dump(temp_json, json_file)
                    json_file.truncate()


    # Copy recorded event files
    if copy_events == "y" :
        bids_copy_events(behav_path, data_root_path, dataset_name)
 
    #Validate paths with BIDSValidator
    #see also http://bids-standard.github.io/bids-validator/
    validator = BIDSValidator()
    os.chdir(target_root_path)
    for file_to_test in  Path('.').glob('./**/*'):
        if file_to_test .is_file():
            file_to_test  = '/'+str(file_to_test )
            print('\nTest the following name of file : {name} with BIDSValidator'.format(name=file_to_test))
            print(validator.is_bids(file_to_test))
    #valider si les unités sont en secondes ?
    
if __name__ == "__main__":
    # Parse arguments from console
    parser = argparse.ArgumentParser(description =
                                     'NeuroSpin to BIDS conversion')
    parser.add_argument('-root_path',
                        type=str,
                        nargs=1,
                        default=[''],
                        help='directory containing exp_info to download to')
    parser.add_argument('-dataset_name',
                        type=str,
                        nargs=1,
                        default=['bids_dataset'],
                        help='desired name for the dataset')
    parser.add_argument('-copy_events',
                        type=str,
                        nargs=1,
                        default=['n'],
                        help='copy events from a directory with the same structure')
    parser.add_argument('-neurospin_database',
                        type=str,
                        nargs=1,
                        default=['prisma'],
                        help='neurospin server to download from')
    # LOAD CONSOLE ARGUMENTS
    args = parser.parse_args()
#    bids_acquisition_download(data_root_path=args.root_path[0],
#                              dataset_name=args.dataset_name[0],
#                              download_database=args.neurospin_database[0],
#                              force_download=False,
#                              behav_path='exp_info/recorded_events',
#                              test_paths=False)
    
    deface = yes_no('\nDo you want deface T1? (y/n)')
      
#    data_root_path='/neurospin/unicog/protocols/IRMf/Unicogfmri/BIDS/test_demo'
#    bids_acquisition_download(data_root_path, deface=True)
    print(args.root_path[0])
    bids_acquisition_download(data_root_path=args.root_path[0],
                              dataset_name=args.dataset_name[0],
                              force_download=False,
                              behav_path='exp_info/recorded_events',
                              copy_events=args.copy_events[0],
                              deface = deface,
                              test_paths=False)