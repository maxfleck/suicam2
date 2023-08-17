import GPy
import numpy as np
import matplotlib.pyplot as plt
import cv2
import pickle
import glob

def norm(z):
    z -= np.min(z)
    z /= np.max(z)
    return z

class filter_gp_0():
    
    def __init__(self, mul=0.9,
                 file_m0="m0.pkl" , 
                 file_m1="m1.pkl" , 
                 file_m2="m2.pkl" ):
        
        self.mul = mul
        
        with open( file_m0, 'rb') as file:
            self.m0 = pickle.load(file)
        with open( file_m1, 'rb') as file:
            self.m1 = pickle.load(file)        
        with open( file_m2, 'rb') as file:
            self.m2 = pickle.load(file)    
            
        return
    
    def get_filters(self, samplesize=1):
        
        xx = np.linspace( 0, 1, 256)
        X = np.atleast_2d(xx).T
        
        sample0 = self.m0.posterior_samples_f(X, full_cov=True, size=samplesize)
        sample1 = self.m1.posterior_samples_f(X, full_cov=True, size=samplesize)
        sample2 = self.m2.posterior_samples_f(X, full_cov=True, size=samplesize)
        
        filter0 = norm( sample0[ :,0,0 ] )*256
        filter1 = norm( sample1[ :,0,0 ] )*256
        filter2 = norm( sample2[ :,0,0 ] )*256
        
        plt.plot(filter0)
        plt.plot(filter1)
        plt.plot(filter2)
        
        
        return filter0,filter1,filter2
    

    def apply_filter(self, img):
        
        mc = np.mean( np.mean( img, axis=0 ), axis=0 ) 
        pmc = np.argsort(mc)

        img = np.array( img*self.mul ).astype(int)
        
        filter0,filter1,filter2 = self.get_filters()
        
        img_filtered = np.empty( img.shape )
        img_filtered[ :,:,pmc[0] ] =  filter2[:][ img[ :,:,pmc[0] ] ]
        img_filtered[ :,:,pmc[1] ] =  filter1[:][ img[ :,:,pmc[1] ] ]
        img_filtered[ :,:,pmc[2] ] =  filter0[:][ img[ :,:,pmc[2] ] ]

        img_filtered  = np.array( img_filtered/self.mul ).astype(int)
        
        #img_enhanced  = np.array( img_filtered*10 ).astype(int)
        #img_filtered  = 0.95*img_filtered + 0.05*img_enhanced
        #img_enhanced  = np.array( img_filtered ).astype(int)
        
        img_filtered[ img_filtered > 250 ] = 250
        img_filtered[ img_filtered < 10 ] = 10

        mc_filtered = np.mean( np.mean( img_filtered, axis=0 ), axis=0 )

        return mc_filtered, img_filtered
        
        #cv2.imwrite(img_out,img_save)
        #Image(filename=img_out) 
