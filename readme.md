# tracky

Simple script that logs when certain user interface elements appear in a video screen recording.

The script uses the [structural simularity index (ssi) as implemented in scikit-image](https://scikit-image.org/docs/0.12.x/auto_examples/transform/plot_ssim.html). 

## Requirements

Required
* Python3
* Python modules: opencv-python (cv2), numpy, scikit-image (skimage)

Recommended
* ffmpeg

Only tested with mp4 (h264) files generated from IOS screen recorder and Android "AZ Screen Recorder".

## Usage

### Video preparation

Screen capture videos have very infrequent (and odd) keyframe intervals which cause issues with the opencv video functions. This mostly causes a problem when seeking to specific times. It's highly recommended to add regular and frequent keyframes to the video before processing. 

Using ffmpeg, add a keyframe every 30 frames to original file:

```console
ffmpeg -i original.mp4 -vcodec libx264 -x264-params keyint=30 -acodec copy fixed.mp4
```

### Specify elements to track

This is currently done manually by editing an associated json configuration video for each video. 

1. Start with the json file template below, save it with the same name as your video (e.g. `capture.json`) in the same directory as the video:

```json
{ 
  "elements": [
    { "name": "name", "time": 0, "roi": [0,0,0,0], "threshold": 0.95 }
  ]
}
```


1. Use a video player like Quicktime or VLC to find a frame in the video with the element you want to track (and in the position you expect it to always be). **Note down the frame time in seconds, and copy or save the frame.**

2. Load the frame into an image editor and locate the x,y pixel position of the top corner of the bounding box and the width and height of the bounding box. For example, in Photoshop you can use a rectangular selection and see this information in the information panel. 

3. Add the element name, frame time where the element appears, and x,y,w,h of the bounding box to the json file for this video. For example, an element named _speech-button_ that appears on a frame at 5s with bounding box top left at 711,1669 with width 68 and height 81 would look like this:

```json
"name": "speech-button", "time": 5, "roi": [711,1669,68,81]
```

4. Do the same for other elements you want to track. It's ok of they overlap. Here's a sample of a finished file with two elements to track:

```json
{ 
  "elements": [
    { "name": "speech-button", "time": 5, "roi": [711,1669,68,81], "threshold": 0.95 },
    { "name": "speech-recording", "time": 41, "roi": [241,1591,333,167], "threshold": 0.95 }
  ]
}
```

### Verify elements are captured correctly

Run the script with the `-debugelms` flag like this:

```console
tracky.py -debugelms capture.mp4
```

This creates a debugdir and with one image for each element. Examine those images to make sure you see a red box around the element. 

If the element isn't in the debug image, it suggests a problem with seeking to the right time. Check your time for the element, and try adding or subtracting a second. If that does't work, scrub to another part of the video and try another time where the element appears in the same position.

### Set the threshold for detecting the element

The default threshold of 0.95 may work ok, but you should check to see by running the script with the  `-debugproc` flag. This will write an image for every processed frame in the debug directory. Each frame image shows all elements with a number for the simularity metric.

To speed this test, use the `-freq`, `-timestart`, and `-timeend` arguments to avoid processing all frames. 

Here's an example to check the threshold by showing every 60th frame for the first 120s:

```console
tracky.py -debugproc -freq 60 -timeend 120 capture.mp4
```

You can scroll throught the images watch how the scores change and adjust the threshold if you see false positives or false negatives. Simularity score ranges from 0 to 1, but even a perfect match isn't always 1 due to invisible artifacts from video compression. 

### Process the video

Process the whole video like this:

```console
tracky.py capture.mp4
```

This will create a CSV file called `output.csv`. It has several columns to check video times and the raw ssi values, but you can ignore those. The columns you need are `time` (frame time in seconds) and the columns named for each of your elements. The element columns are `1` if that element is in the frame and `0` otherwise. 

Processing the whole video can be slow, you can use the `-freq` tag to skip frames and speed it up. Of course, this will reduce the time resolution of detecting elements. 

### Other flags and settings

Use the `--help` flag to see all available flags and arguments.

```console
tracky.py --help
```









