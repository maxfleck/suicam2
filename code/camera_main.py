import RPi.GPIO as GPIO
import usb
import glob, os
import time
from multiprocessing import Process, active_children
import neopixel
import board
import picamera
import picamera.array
#import matplotlib.image
import cv2
import numpy as np
from scipy import ndimage
from filter import filter_gp_0

GPIO.cleanup() 
GPIO.setmode(GPIO.BCM)

class usb_mount():
    """
    usb_mount class
    
    the whole software of the camera is build around the availability
    of an usb storage device as if pictures can be taken and safed depends on this.
    
    
    
    """
    
    def __init__(self, mount_folder, filter_fun, pixel_pin, 
                 color=(255, 0, 0) ):
        """
        Initializing the usb_mount class
        
        - theres a lot of hard coded stuff right now
        - ... but it works
        
        """
        self.camera = picamera.PiCamera()
        
        self.pixel = neopixel.NeoPixel(pixel_pin, 1,)
        self.pixel[0] = color

        self.usb_status = False
        self.umount()
        self.mount_folder = mount_folder
        
        self.save_folder_raw     = mount_folder+"/suicam2_raw/"
        self.save_folder_filter  = mount_folder+"/suicam2_filter/"
        self.save_folder_frame   = mount_folder+"/suicam2_frame/"
        
        self.picname = "pic_"
        self.filter_fun   = filter_fun
        
        # part of the called function
        self.color_take      = (255,0,0)
        self.color_post_take = (255,255,255)        
        # part of color setter 
        self.color_nousb     = (255,0,0)
        self.color_usb       = (0,255,0)
        self.color_camoff    = (0,0,255)
        self.color_children  = (32,200,150)

        #no = self.get_no_children()
        #print("ini no of children:",no)
        self.active_children = False
        self.active_camera = False

        #
        self.res = (1312,976) # ( vertical, horizontal )
        self.res_shift_horizontal = 40
        self.res_shift_vertical   = 240
        self.res_pic_xy           = 800
        #self.rres_plus = self.res + 2*self.res_shift
        #self.camera.resolution = ( self.rres_plus )
        self.camera.resolution = self.res
        
        self.stream = picamera.array.PiYUVArray(self.camera)
        
        self.active_action = True
        self.active_last_seconds = time.time()
        self.start_camera()
        
        self.rotate_img = 267.5
        self.rotate_img = 272.5
        
        self.trigger_count = 2
        self.no = -1
        return


    def mount(self):
        """
        mounts usb device
        """        
        devices = glob.glob("/dev/sd*")
        for device in devices:
            flag = os.system("sudo mount "+device+" "+self.mount_folder)
            if flag == 0:
                print("mounted",device)
                if not os.path.exists(self.save_folder_filter):
                    os.mkdir(self.save_folder_filter)
                if not os.path.exists(self.save_folder_raw):
                    os.mkdir(self.save_folder_raw)                    
                self.start_camera()
                
                old_imgs_raw    = glob.glob( self.save_folder_raw+self.picname+"*" )
                old_imgs_filter = glob.glob( self.save_folder_filter+self.picname+"*" )
                nos = []
                for old_img in old_imgs_raw:
                    nos.append( int( old_img.split(".")[-2].split("_")[-1] ) ) 
                for old_img in old_imgs_filter:
                    nos.append( int( old_img.split(".")[-2].split("_")[-1] ) )                     
                if nos:
                    self.no = int(np.max(nos)+1)
                else:
                    self.no = 0
                return flag
        return -1 

    def umount(self):
        """
        unmounts usb device
        
        (call this fun when usb remove is detected)
        
        """
        devices = glob.glob("/dev/sd*")
        for device in devices:
            os.system("sudo umount "+device)
        self.stop_camera()
        return

    def get_devno(self):
        """
        gets number of USB devices
        """
        devs = usb.core.find(find_all=True, bDeviceClass=0)
        self.devno = len( list(devs) )        
        return
    
    def check_devices(self):
        """
        checks if USB is available
        mounts...
        ...or unmounts
        """
        self.get_devno()
        #print("number of devs:", devno)
        if self.devno==0 and self.usb_status :
            #print("no devs.. umount")
            self.umount()
            self.usb_status = False
            self.time_event()
            return 1
        elif self.devno>0 and not self.usb_status:
            #print("found devs")
            flag = self.mount()
            if flag == 0:
                self.usb_status = True
                self.time_event()
                return 1
            else:
                self.usb_status = False
        return 0
    
    def knob_function_to_be_called( self, gpio_pin_no ):
        """
        this function is called when the knob is pressed:
        
        there are 4 things that need to be true for the cam to be triggered:
        
        - trigger_count needs to be correct. 
            - for some knobs the function is triggered twice
            - high bouncetimes are no solution
            - ... we need to count the triggers
            - usually every 2nd call is a true call
        - the camera needs to be active (active_action == True)
        - the camera needs not to be in use (active_camera == False)
        - a USB storage device needs to be plugged in and mounted
        
        when the photo was taken a subprocess is started to do the postprocessing
        i.e. apply filters and save the result to the storage device
            
        gpio_pin_no is a dummy and not needed because the pin used is predefined
        
        """
        print("\nKNOB PRESSED",self.no)
        self.trigger_count += 1
        if self.trigger_count % self.trigger_count == 0:
            if self.active_action and not self.active_camera:
                print("KNOB activated\n")      
                if self.usb_status: #and self.get_no_children() < 10:
                    self.pixel[0] = self.color_take
                    self.active_camera = True
                    self.camera.capture(self.stream, 'yuv',) #resize=(320, 240)            
                    self.pixel[0] = self.color_post_take
                    self.stream.truncate()   

                    img = self.stream.rgb_array
                    self.stream.seek(0) 

                    Process(target=self.filter_wrapper, args=(img,self.no) ).start()
                    self.no = self.no + 1

                    self.active_camera = False
                else:
                    self.check_devices()         
                    self.blink(0.1, 3)
        else:
            print("NOOOT activated\n") 
        self.time_event()
        self.color_setter()
        return
    
    def stop_camera(self):
        """
        calling this fun stops the camera
        """
        print("stop camera")
        self.camera.stop_preview()
        return
    
    def start_camera(self):
        """
        calling this fun starts the camera
        """        
        print("start camera")
        self.camera.start_preview()
        time.sleep(1.)
        print("camera ready")
        return
    
    def filter_wrapper(self,img,no):
        """
        - rotates picture
        - trims picture according to camera viewfinder
        - wraps filter fun :)
        - saves results
        - syncs storage device
        
        img: np.array with rgb values for each pixel
        
        no: int for unique savename
        
        """
        print("postproc called",no)
        img = ndimage.rotate(img, self.rotate_img )
        img = img[ self.res_shift_vertical:self.res_pic_xy+self.res_shift_vertical, 
                  self.res_shift_horizontal:self.res_pic_xy+self.res_shift_horizontal ,:]
        
        save_path_raw    = self.save_folder_raw+self.picname+str(no)+".png"
        save_path_filter = self.save_folder_filter+self.picname+str(no)+".png"
        save_path_frame  = self.save_folder_frame+self.picname+str(no)+".png"
        
        # write raw to file
        cv2.imwrite( save_path_raw , cv2.cvtColor(img, cv2.COLOR_RGB2BGR) )
        # apply filter
        _, img_filter = self.filter_fun.apply_filter(img)
        # write filtered to file
        cv2.imwrite( save_path_filter , cv2.cvtColor(img_filter, cv2.COLOR_RGB2BGR) )
        os.system("sync")
        time.sleep(1)
        print("postproc done :)",no)
        return
    
    def get_no_children(self):
        """
        detects and counts running child processes
        """
        children = active_children()
        no = len(children)
        return no
    
    def check_children(self):
        """
        detects if there are running child processes
        """        
        children = active_children()
        no = len(children)
        if no == 0 and self.active_children:        
            self.active_children = False
            return 1
        elif no > 0 and not self.active_children:
            self.active_children = True
            return 1
        return 0

    def color_setter(self):
        """
        color setter fun for rgb pixel
        
        adjusts color of the status LED based on flags
        
        RULE for clear code:
        
        ONLY this fun and the fun triggered when the knob is pressed
        should manipulate the color of the status LED !!
        
        """
        if self.usb_status:
            if not self.active_action:
                print("not active", self.color_camoff)
                self.pixel[0]      = self.color_camoff
                self.current_color = self.color_camoff
            elif self.active_children:
                print("children", self.color_children)
                self.pixel[0]      = self.color_children
                self.current_color = self.color_children                   
            else:
                print("usb", self.color_usb)
                self.pixel[0] = self.color_usb
                self.current_color = self.color_usb
        else:
            print("no usb")
            self.pixel[0] = self.color_nousb
            self.current_color = self.color_nousb
        print("current_color:", self.current_color )
        return
    
    def blink(self, zzz, times):
        """
        makes the LED flash at a certain frequency
        
        might be unused...
        ...dont use !
        
        """
        for _ in range(times):
            self.pixel[0] = (0,0,0)
            time.sleep( zzz )
            self.pixel[0] = self.current_color
            self.pixel.show()
            time.sleep( zzz )
        return
    
    def time_event(self):
        """
        call this fun when something happens
        
        based on the last time event the cam will go to sleep
        
        """
        self.active_action = True
        self.active_last_seconds = time.time()
        return
    
    def check_active_time(self, time_to_sleep=60):
        """
        checks when the last event happened
        
        if it is too far back the camera is sent to sleep
        
        time_to_sleep: 
        - time in seconds
        - after this time the cam goes to sleep
        
        """
        time_diff = time.time() - self.active_last_seconds
        if time_diff > time_to_sleep and self.active_action:
            self.active_action = False
            self.stop_camera()
            return 1
        return 0
        

try:

    pixel_pin = board.D10
    knob_input_pin = 14    
    bouncetime = 100 #300
    
    gpf = filter_gp_0()
    
    usbmt = usb_mount("/home/pi/usb_tests/usb_mount/",gpf,pixel_pin)

    usbmt.check_devices()
    usbmt.check_children()
    usbmt.color_setter()

    # play around with rise and fall... avoid double trigger??
    GPIO.setup(knob_input_pin, GPIO.IN , pull_up_down=GPIO.PUD_UP)    
    GPIO.add_event_detect( knob_input_pin, GPIO.RISING, 
                          callback=usbmt.knob_function_to_be_called, bouncetime=bouncetime)

    zzzz = .3
    while True:
        if not usbmt.active_camera:
            flag0 = usbmt.check_devices()
            flag1 = usbmt.check_children()
            flag2 = usbmt.check_active_time()
            if flag0==1 or flag1==1 or flag2==1:
                print("status changed \n")
                usbmt.color_setter()
        time.sleep(zzzz)        

except Exception as e:
    print("errorlog:")
    print( str(e) )
    nos = []
    old_logs = glob.glob( "LOG_*" )
    if len(old_logs) > 0:
        for old_log in old_logs:
            nos.append( int( old_log.split("_")[-2] ) )
        no = int( np.max(nos)+1 )
    else:
        no = 0
    logf = open("LOG_"+str(no), "w")
    logf.write( str(e) )
    logf.close()
    GPIO.cleanup()
    print("error")
