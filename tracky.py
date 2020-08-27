#!/usr/bin/env python3
"""Track when specific elements are in frame at a specific position.
"""

import os
import sys
import argparse

import numpy as np
import cv2
from skimage.metrics import structural_similarity as ssim
from skimage import metrics as skm
from pathlib import Path
import json
import shutil

# parameters

# # video filename
# video_filename = 'test-videos/android1-fixed.mp4'
# # json filename to use (default is video filename stem)
# data_filename = 'test-videos/android3.json'
# # csv output filename (default is video filename stem)
# output_filename = None
# # timecode offest in s for logging, useful to sync with other log (default is 0)
# timecode_offset = 0
# # start time in s for processing (default is 0)
# time_start = 0
# # end time in s for processing (default is duration of video)
# time_end = 0
# write elm images to subdirectory (default false)
# debug_elements = True
# # write processing images to subdirectory (default false)
# debug_processing = True
# debug_processing_freq = 10
# # directory for debug output folders (default is same dir as video)
# debug_dir = '/Users/dan/nobackup/tracky-testvideos'


debug_colour = (0,0,255)
debug_font = cv2.FONT_HERSHEY_SIMPLEX


def main(arguments):

    parser = argparse.ArgumentParser(
        description = __doc__,
        usage = '%(prog)s [options] videofile',
        formatter_class = argparse.RawDescriptionHelpFormatter
        )

    parser.add_argument('videofile', 
                         help = "video file to process", 
                         metavar = 'FILE',
                         type = str)

    parser.add_argument('-datafile',
                        help = 'json data file',
                        metavar = 'FILE',
                        type = str)                         

    parser.add_argument('-outfile',
                        help = 'csv output file',
                        metavar = 'FILE',
                        type = str)    

    parser.add_argument('-timestart',
                        help = 'start processing at T seconds',
                        metavar = 'T',
                        default = 0,
                        type = float)               

    parser.add_argument('-timeend',
                        help = 'end processing at T seconds',
                        metavar = 'T',
                        type = float)  

    parser.add_argument('-timeoffset',
                        help = 'add T seconds to log file (useful to synch to other event log)',
                        metavar = 'T',
                        default = 0,
                        type = float)  

    # debug args

    parser.add_argument('-debugdir',
                        help = 'parent directory to create directory of debug images',
                        metavar = 'DIR',
                        type = str)                            

    parser.add_argument('-debugelms',
                        help = 'save images to debugdir showing frame and location for each element to track',
                        action = 'store_true')    

    parser.add_argument('-debugproc',
                        help = 'save images to debugdir of frames showing elements and their simulariy scores',
                        action = 'store_true')  

    parser.add_argument('-freq',
                        help = 'process every N frames (useful for testing and debugging)',
                        metavar = 'N',
                        default = 1,
                        type = int)   

    # # control output
    # verbose = True
    # quiet = False                        

    global args
    args = parser.parse_args(arguments)
    print(args)

    print(args.videofile)

    # open video file
    cap = cv2.VideoCapture(args.videofile)
    global fps
    fps = cap.get(cv2.CAP_PROP_FPS) 
    # show basic info about video   
    global spf 
    spf = 1.0/fps # seconds per frame
    frame_count = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    duration = frame_count/fps
    ret, frame = cap.read()
    height, width = frame.shape[:2]
    print('  {:.5f} fps, {} frames, ({:.5f} spf) {:.0f}:{:.3f} (M:S) {:.3f} (S))'
        .format(fps, frame_count, spf, int(duration/60), duration%60, duration))
    print('  {} x {} pixels'
        .format(width, height)) 

    # set max duration to default      
    if not args.timeend:
        args.timeend = duration
        
    # set datafile filename to default 
    if not args.datafile:
        p = Path(args.videofile)
        args.datafile = str(p.parent / p.stem) + '.json'

    # load json datafile 
    global data
    with open(args.datafile, 'r') as f:
        data = json.load(f)    
        
    # show info about data file
    print(args.datafile)
    print(json.dumps(data, indent=1))

    # set output filename
    if not args.outfile:
        p = Path(args.videofile)
        args.outfile = str(p.parent / p.stem) + '.csv'

    cap.release()

    # create debug directory if needed
    if args.debugelms or args.debugproc:
        p = Path(args.videofile)    
        
        # create default debug dir
        if not args.debugdir:
            args.debugdir = str(p.parent)
            
        args.debugdir += '/' + str(p.stem) + '-debug'
        
        # remove dir if already there
        try: 
            shutil.rmtree(args.debugdir)
        except FileNotFoundError as e:
            pass

        # create it
        Path.mkdir(Path(args.debugdir), exist_ok = True)

        print('debugdir: "{}"'.format(args.debugdir))

    # do the processing
    set_elements()

    if not args.debugelms:
        process()

def set_elements():

    cap = cv2.VideoCapture(args.videofile)

    for elm in data['elements']:

        t = elm['time']
        r = elm['roi']

        print('{} {}s'.format(elm['name'], t))

        ret = cap.grab()

        seek = t * 1000
        cap.set(cv2.CAP_PROP_POS_MSEC, seek)
        ret, frame = cap.read()
        pos = cap.get(cv2.CAP_PROP_POS_MSEC)
        print('by msec: set {:.3f}, get {:.3f}'.format(seek/1000, pos/1000))
        
        elm['roi-template']= frame[r[1]:r[1]+r[3], r[0]:r[0]+r[2]]

        if args.debugelms:

            # imshow(elm['roi-template'])
            debug = cv2.rectangle(frame, (r[0], r[1]), (r[0]+r[2], r[1]+r[3]), debug_colour, 1)
            # imshow(debug) 
            cv2.imwrite(args.debugdir + '/element {}.png'.format(elm['name']), debug) 

    cap.release()   


def process():

    cap = cv2.VideoCapture(args.videofile)

    out  = open(args.outfile, 'w') 

    out.write('time,frame,frame_video,time_video,frame_chk,time_chk,')  

    for elm in data['elements']:
        out.write(elm['name'] + '_ssi,')
        out.write(elm['name'] + ',')
    out.write('\n')

    update_freq = 100

    f = 0
    t = 0
    i = 0
    num = int((args.timeend - args.timestart) * fps)

    print('processing {} frames, {}s to {}s'.format(num, args.timestart, args.timeend))

    while(cap.isOpened()):

        ret = cap.grab()
        if not ret:
            break
            
        pos_f = cap.get(cv2.CAP_PROP_POS_FRAMES) - 1
        pos_s = (cap.get(cv2.CAP_PROP_POS_MSEC) / 1000) - spf
        
        if t > args.timeend:
            break    
        
        if t <= args.timestart:
            if f % update_freq == 0:
                print(' seek {} {:.3f}'.format(f, t))
            t += spf
            f += 1
            i = 1
            continue
        

        if i % update_freq == 0:
            print(' proc {} of {} - {} ({:.0f}) {:.3f} ({:.3f})'.format(i, num, f, pos_f, t, pos_s))

        # process frame
        if i % args.freq == 0:

            ret, frame = cap.retrieve()    
    
            out.write(','.join(map(str, ['{:.3f}'.format(t + args.timeoffset), 
                                        i,
                                        f, 
                                        '{:.3f}'.format(t), 
                                        pos_f, 
                                        '{:.3f}'.format(pos_s) ])))    
            
            if args.debugproc:
                debug = frame.copy()
            
            for elm in data['elements']:
                
                r = elm['roi']
                roi_template = elm['roi-template']
                roi_image = frame[r[1]:r[1]+r[3], r[0]:r[0]+r[2]]
                
                # ssi
                (score, diff) = skm.structural_similarity(roi_template, roi_image, full = True, multichannel = True)
                exists = score > elm['threshold'] 
        #         # mse
        #         (score) = skm.mean_squared_error(roi_template, roi_image)
        #         scores['mse'] = ',{:.2f}'.format(score)
                
                out.write(',{:.2f}'.format(score))
                out.write(',{}'.format('1' if exists else '0'))        

                
                if args.debugproc:
                    s = '{:.2f}'.format(score)
                    stroke_thickness = 3 if exists else 1  
                    debug = cv2.rectangle(frame, (r[0], r[1]), (r[0]+r[2], r[1]+r[3]), debug_colour, stroke_thickness)
                    debug = cv2.putText(debug, s, (r[0], r[1]-5), debug_font, 0.6, debug_colour, 1)
            
            if args.debugproc:
                cv2.imwrite(args.debugdir + '/{:05d} {:.3f}.png'.format(f, t), debug)   

            out.write('\n')
        
        t += spf
        f += 1
        i += 1
        
    cap.release()
    out.close()

    # cv2.destroyAllWindows()

    print(' done')     

if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))