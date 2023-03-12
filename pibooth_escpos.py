# -*- coding: utf-8 -*-

"""pibooth plugin for printing pictures on a thermal printer"""

import csv
import math
import tempfile
import os
import uuid

import pibooth
from pibooth.utils import LOGGER

from escpos import config
from escpos.printer import Dummy

from PIL import Image, ImageOps

__version__ = "1.0.0"

SECTION = 'ESCPOS'
FIELDNAMES = ['picture', 'token']


@pibooth.hookimpl
def pibooth_configure(cfg):
    """Declare the new configuration options"""
    cfg.add_option(SECTION, 'copies', 2, "How many copies?")
    cfg.add_option(SECTION, 'print_qr', True, "Print a QR Code with the link?")
    cfg.add_option(SECTION, 'qr_URL', '', "The URL string used for the qr code. Supports formatting, inserts filename (name) and a generated token (token).")
    cfg.add_option(SECTION, 'db_file', 'token.csv', "Absolute path to file that stores the filename token combinations")


@pibooth.hookimpl
def pibooth_startup(app, cfg):
    """Verify that db file is there"""

    copies = cfg.getint(SECTION, 'copies')
    print_qr = cfg.getboolean(SECTION, 'print_qr')
    qr_URL = cfg.get(SECTION, 'qr_URL')
    db_file = cfg.getpath(SECTION, 'db_file')

    if not qr_URL:
        LOGGER.error("QR URL not defined in ["+SECTION+"][qr_URL], QR printing disabled")
    else:
        LOGGER.info(SECTION + ": Initializing escpos printer plugin")
        LOGGER.info(SECTION + ": Copies: {}".format(copies))
        LOGGER.info(SECTION + ": Print QR: {}".format(print_qr))
        LOGGER.info(SECTION + ": QR URL: {}".format(qr_URL))
        LOGGER.info(SECTION + ": DB File: {}".format(db_file))
        if not os.path.exists(db_file):
            LOGGER.info(SECTION + ": DB file {} not found. Creating it with header.".format(db_file))
            with open(db_file, 'w', newline='') as fd:
                writer = csv.DictWriter(fd, fieldnames=FIELDNAMES)
                writer.writeheader()
            
        app.escpos_printer = config.Config().printer()
        app.escpos_copies = copies
        app.escpos_print_qr = print_qr
        app.escpos_qr_URL = qr_URL
        app.escpos_db_file = db_file



@pibooth.hookimpl
def state_processing_exit(app, cfg):
    """Print Picture"""
    name = os.path.basename(app.previous_picture_file)

    if app.escpos_db_file:
        token = uuid.uuid4()
        with open(app.escpos_db_file,'a') as fd:
            db = csv.writer(fd)
            db.writerow([name, token])
    # Print the image
    im = app.previous_picture
    max_width = int(app.escpos_printer.profile.profile_data["media"]["width"]["pixels"])
    if im.height < im.width: # landscape, needs to be rotated
        im = im.rotate(90, expand=True)
    im = ImageOps.contain(im, (max_width, 3000))
    if app.escpos_printer.profile.profile_data["features"]["graphics"]:
        impl = "graphics"
    elif app.escpos_printer.profile.profile_data["features"]["bitImageRaster"]:
        impl = "bitImageRaster"
    else:
        impl = "bitImageColumn"
    
    for i in range(app.escpos_copies):
        app.escpos_printer.image(im, impl=impl)
        if app.escpos_print_qr:
            app.escpos_printer.cut(mode="PART")
            app.escpos_printer.set(align='left')
            app.escpos_printer.text("Download: " + app.escpos_qr_URL.format(name=name, token=token))
            app.escpos_printer.qr(app.escpos_qr_URL.format(name=name, token=token), center=True, impl=impl)
            app.escpos_printer.set(align='center')
            app.escpos_printer.text("Scan me!")
        if i != app.escpos_copies - 1:
            app.escpos_printer.cut(mode="PART")
    # PART for vertical mount; FULL for horizontal
    app.escpos_printer.cut(mode="PART")


@pibooth.hookimpl
def pibooth_cleanup(app):
    app.escpos_printer.close()
