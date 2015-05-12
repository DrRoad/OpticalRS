# -*- coding: utf-8 -*-
"""
Created on Fri Jun 27 11:28:21 2014

This file will implement methods from Lyzenga 1981. Unless otherwise stated
methods will expect image arrays in the shape of (Rows,Columns,Bands).

Lyzenga, D.R., 1981. Remote sensing of bottom reflectance and water attenuation 
parameters in shallow water using aircraft and Landsat data. International 
Journal of Remote Sensing 2, 71–82. doi:10.1080/01431168108948342

@author: jkibele
"""

import numpy as np
from math import sqrt
from fractions import Fraction
from decimal import Decimal
from itertools import combinations
from matplotlib import pyplot as plt
from scipy import odr

##-- Straight from the paper --##
## The following 2 methods are meant to implement methods explicitly described
## in Lyzenga 1981.

def attenuation_coef_ratio(band_i,band_j):
    r"""
    Calculate the attenuation coefficient ratio as described in Lyzenga (1981).
    You should supply this function with arrays that are drawn from an area of
    uniform bottom type and varying depth. Sand is usually pretty easy to 
    identify and seems to be the substrate of choice for this sort of thing. 
    For details see equations 4, 5, and 6 of Lyzenga 1981.
    
    Args:
        band_i (numpy.array): array of reflectance values over a uniform stubstrate
            and varying depths for band i (whatever band you choose).
            
        band_j (numpy.array): array of reflectance values over the same area as band
            i from a different band, j.
            
    Returns:
        float. The attention coeffiecient ratio Ki/Kj. Described in equation 4
        of Lyzenga 1981.
    
    .. math::
        \frac{k_i}{k_j} = a + \sqrt{ a^2 + 1 }
        where:
        a = \frac{ \sigma_i - \sigma_j }{ 2\sigma_{ij} }
        
    :math:`\sigma_i` is the variance of :math:`band_i`, :math:`\sigma_j` is the
    variance of :math:`band_j` and :math:`\sigma_{ij}` is the covariance between
    :math:`band_i` and :math:`band_j`.
    """
    if np.ma.is_masked(band_i):
        band_i = band_i.compressed()
    else:
        band_i = band_i.ravel()
        
    if np.ma.is_masked(band_j):
        band_j = band_j.compressed()
    else:
        band_j = band_j.ravel()
        
    band_i = np.log(band_i)
    band_j = np.log(band_j)
        
    cov_mat = np.cov(band_i,band_j)
    i_var = cov_mat[0,0]
    j_var = cov_mat[1,1]
    ij_cov = cov_mat[0,1]
    a = (i_var - j_var) / ( 2.0 * ij_cov )
    #print "a=%f" % a
    att_coef = a + sqrt( a**2 + 1 )
    return att_coef
    
def di_index(imarr,sandarr,i,j):
    r"""
    This method implements equation 2 from Lyzenga 1981 to generate a single depth
    invariant index from a pair of bands.
    
    Args:
        imarr (numpy.array): This is the image array of shape (Rows,Cols,Bands)
        
        sandarr (numpy.array): This is an array image array that contains only
            pixels from a uniform bottom type (usually sand) and varying depth.
            Values from this array will be passed to the attenuation_coef_ratio
            method.
            
        i (int): The zero indexed band number for the first band to be included 
            in the calculation of the index. 
            
        j (int): The zero indexed band number for the second band to be included 
            in the calculation of the index.
    """
    atr = attenuation_coef_ratio(sandarr[:,:,i],sandarr[:,:,j])
    fr = Fraction(Decimal(atr))
    Ki,Kj = fr.numerator,fr.denominator
    Bi = imarr[:,:,i]
    Bj = imarr[:,:,j]
    DI = ( Kj * np.log(Bi) - Ki * np.log(Bj) ) / sqrt( Ki**2 + Kj**2 )
    return DI
    
##-- Implied by Lyzenga 1981 --##
## The following method simply applies Lyzenga's methods to a mulitspectral
## image. This may be more convenient that manually running di_index for 
## each band combination.
    
def di_indexes_bandarr(imarr,sandarr,n_bands,subset_slice=None,pix_band_shaped=False):
    """
    Generate a depth invariant index image for each possible band combination
    and output as a multispectral array of shape (Rows,Columns,Combos). Also 
    return a list integer tuples of band combinations.
    
    Args:
        imarr (numpy.array): This is the image array of shape (Rows,Cols,Bands)
        
        sandarr (numpy.array): This is an array image array that contains only
            pixels from a uniform bottom type (usually sand) and varying depth.
            Values from this array will be passed to the attenuation_coef_ratio
            method.
        
        n_bands (int): The number of bands you want to generate indexes for.
            There generally doesn't seem to be much point in including the NIR
            bands.
            
        subset_slice (numpy.s_ index expression): If provided, only this subset
            of the array will be used to calculate the indexes. This is useful
            for testing things out if processing is slow. For example, 
            np.s_[1300:1800,1200:2400] would subset image rows 1300 - 1800 and
            columns 1200 - 2400.
            
        pix_band_shaped (bool): If true, indexes will be flattened. Rather than
            returning (Rows,Columns,N Combos) shape, (N Pixels, N Combos) shape
            will be returned.
            
    Returns:
        di_index_array (numpy.array): An array of depth invariant indexes. The
            last dimension of the array corresponds to which combination of bands 
            created that index. For instance (assuming pix_band_shaped=False),
            di_index_array[:,:,x] was created by combos[x].
            
        combos (list of tuples): A list of tuples of integers. The integers are
            zero indexed band numbers. If combos[x] = (0,1), then 
            di_index_array[:,:,x] was created with imarr band 0 and band 1.
    """
    if subset_slice:
        imarr = imarr[subset_slice]
    combos = [cb for cb in combinations( range(n_bands), 2 ) ]
    n_combos = len( combos )
    arrdtype = imarr.dtype
    out_arr = np.empty((imarr.shape[0],imarr.shape[1],n_combos),dtype=arrdtype)
    for ind,bc in enumerate( combos ):
        i,j = bc
        di_ind = di_index(imarr,sandarr,i,j)
        out_arr[:,:,ind] = di_ind
    if pix_band_shaped:
        out_arr = out_arr.reshape( out_arr.shape[0]*out_arr.shape[1], -1 )
    return out_arr, combos
    
def lin_odr(x,y):
    """
    Simple version of Orthoganal Distance Regression for y=mx+b.
    
    Args:
        x (array): x values
        y (array): y values
        
    Returns:
        slope: m in y=mx+b
        intercept: b in y=mx+b
        res_var: Residual Variance. Apparently a measure of goodness
            of fit. Smaller values mean better fit.
            
    Notes: The scipy.odr package has a lot of options. This is a
        much simplified, narrowed down useage. Check [here](http://docs.scipy.org/doc/scipy/reference/odr.html)
        for more documentation or, for even more, check [here](http://docs.scipy.org/doc/external/odrpack_guide.pdf).
    """
    def lf(B,x):
        return B[0]*x + B[1]
    linmod = odr.Model(lf)
    mydata = odr.RealData(x,y)
    myodr = odr.ODR(mydata,linmod,beta0=[1.,2.])
    myout = myodr.run()
    slope,intercept = myout.beta
    return slope, intercept, myout.res_var
    
def plot_band_combos(sandarr,n_bands,apply_log=True,figsize=(15,15)):
    if apply_log:
        logarr = np.log( sandarr[:,:,:n_bands] )
    else:
        logarr = sandarr[:,:,:n_bands]
    logmax = logarr.max()
    logmin = logarr.min()
    fig,axarr = plt.subplots(n_bands-1,n_bands-1,figsize=figsize,sharex=True,sharey=True,frameon=False)
    for i,j in combinations(range(n_bands),2):
        if np.ma.is_masked:
            x,y = logarr[:,:,i].compressed(),logarr[:,:,j].compressed()
        else:
            x,y = logarr[:,:,i].ravel(),logarr[:,:,j].ravel()
        axarr[i,j-1].set_axis_off()
        ax = axarr[j-1,i]
        ax.set_axis_on()
        ax.scatter(x,y,alpha=0.01,c='steelblue',marker='o')
        ax.set_xlim(logmin,logmax)
        ax.set_ylim(logmin,logmax)
        xl = r"band %i" % (i + 1)
        yl = r"band %i" % (j + 1)
        ax.set_xlabel(xl)
        ax.set_ylabel(yl)
        ax.set_frame_on(False)
        odrslope,odrinter,odr_res_val = lin_odr(x,y)
        odrline = lambda x: odrslope*x + odrinter
        xmm = np.array([x.min(),x.max()])
        ax.plot(xmm,odrline(xmm),c='r')
        plt.tight_layout()