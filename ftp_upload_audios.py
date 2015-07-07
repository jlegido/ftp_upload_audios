#!/usr/bin/python

from configobj import ConfigObj
from base64 import b64decode
from ftplib import FTP
from os import listdir, rename
from os.path import join, isdir, basename, splitext
from subprocess import check_output, CalledProcessError
from logging import getLogger, FileHandler, Formatter, INFO
from datetime import date, datetime, timedelta

class NoAudioFile(Exception):
    def __init__(self, value):
        self.value = value
    def __str__(self):
        return repr(self.value)

class WrongFilenameFormat(Exception):
    def __init__(self, value):
        self.value = value
    def __str__(self):
        return repr(self.value)

def if_day_ok_format_filename(audio_dir, program, filename):
    "Validates date format and program in yyyymmdd-programname.mp3"
    path_file = join(audio_dir, program, filename)
    broadcast_date = path_file.split('/')[-1].split('-')[0]
    if broadcast_date == yesterday:
        # Let's check file name is the program name
        name, extension = splitext(filename)
        program_name = '-%s' %(program)
        if name.replace(broadcast_date, '', 1) != program_name:
            # Rename the file
            formatted_filename = '%s%s%s' %(broadcast_date, program_name,
                                                                     extension)
            # Rename the file
            rename(join(audio_dir, program, filename),
                   join(audio_dir, program, formatted_filename))
            filename = formatted_filename
    else:
        raise WrongFilenameFormat(path_file)
    return filename

def get_audio_type(path_file):
    "Returns either .mp3 or .ogg"
    file_type = check_output(['file', path_file]).split(': ')[1].strip()
    if any(tag in file_type for tag in config['audio_tags']['mp3']):
        return '.mp3'
    elif any(tag in file_type for tag in config['audio_tags']['ogg']):
        return '.ogg'
    raise NoAudioFile(path_file)

def if_audio_ensure_mp3(path_file):
    "If audio file makes sure is .mp3 file, if not it converts to it"
    # TODO: sndhdr not working
    # https://docs.python.org/2/library/sndhdr.html#module-sndhdr
    try:
        if get_audio_type(path_file) == '.ogg':
            path_file_ogg, extension_ogg = splitext(path_file)
            path_file_mp3 = path_file_ogg + '.mp3'
            try:
                # Debian
                check_output(['ffmpeg', '-y', '-loglevel', '-8', '-y', '-i',
                             path_file, '-acodec', 'libmp3lame', path_file_mp3])
                ''' Ubuntu
                check_output(['avconv', '-y', '-loglevel', 'quiet', '-i',
                             path_file, '-c:a', 'libmp3lame', '-q:a', '2',
                             path_file_mp3])
                '''
            except CalledProcessError, e:
                logger.error(
                     'Error converting from .ogg to .mp3 %s. Eception: %s'\
                             %(path_file, e))
            return path_file_mp3
    except NoAudioFile:
        raise
    return path_file

def ftp_upload(dir, filename):
    "Uploads path_local_file"
    ftp = FTP()
    ftp.connect(b64decode(config['ftp']['host']),
                b64decode(config['ftp']['port']))
    ftp.login(b64decode(config['ftp']['user']),
              b64decode(config['ftp']['password']))
    file = open(join(dir, filename), 'rb')
    ftp.storbinary('STOR %s' %(filename), file)
    file.close()
    ftp.quit()
    logger.info('FTP uploaded successfully: %s' %(join(dir, filename)))

config = ConfigObj('config')

handler = FileHandler(config['dir']['log'])
logger = getLogger('audio_date_formatter')
formatter = Formatter( '%(asctime)s - %(lineno)s: %(levelname)s %(message)s' )
handler.setFormatter(formatter)
logger.addHandler(handler)
logger.setLevel(INFO)

ftp = FTP()

yesterday = (date.today() - timedelta(days=int(config['days_back']))).\
            strftime(config['broadcast_date_format'])

for dir in listdir(config['dir']['local']):
    path_dir = join(config['dir']['local'],dir)
    try:
        file_list = listdir(path_dir)
    except OSError as e:
        logger.warning('File instead of a directory: %s' %(e))

    if isdir(path_dir) and (len(file_list) > 0) and\
    not any(dir in ignored_dir for ignored_dir in config['dir']['ignore']):
        program = dir
        next_broadcast = ''
        for file in file_list:
            path_file = join(config['dir']['local'], dir, file)
            try:
                path_file = if_audio_ensure_mp3(path_file)
            except NoAudioFile:
                if config['dir'] == 'remove':
                    # TODO: implement
                    pass
                logger.warning('No audio file. Ignoring "%s"' % (path_file))
            else:
                # TODO: I need to set again file variable, since it can .mp3
                file = basename(path_file)
                try:
                    file = if_day_ok_format_filename(config['dir']['local'],
                                                    dir, file)
                except WrongFilenameFormat:
                    pass
                else:
                    ftp_upload(join(config['dir']['local'], dir), file)
