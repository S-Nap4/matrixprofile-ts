# -*- coding: utf-8 -*-
from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

range = getattr(__builtins__, 'xrange', range)
# end of py2 compatability boilerplate

import numpy as np
import numpy.fft as fft

def zNormalize(ts):
    """
    Returns a z-normalized version of a time series.

    Parameters
    ----------
    ts: Time series to be normalized
    """

    ts -= np.mean(ts)
    std = np.std(ts)

    if std == 0:
        raise ValueError("The Standard Deviation cannot be zero")
    else:
        ts /= std

    return ts

def zNormalizeEuclidian(tsA,tsB):
    """
    Returns the z-normalized Euclidian distance between two time series.

    Parameters
    ----------
    tsA: Time series #1
    tsB: Time series #2
    """

    if len(tsA) != len(tsB):
        raise ValueError("tsA and tsB must be the same length")

    return np.linalg.norm(zNormalize(tsA.astype("float64")) - zNormalize(tsB.astype("float64")))

def movmeanstd(ts,m):
    """
    Calculate the mean and standard deviation within a moving window passing across a time series.

    Parameters
    ----------
    ts: Time series to evaluate.
    m: Width of the moving window.
    """
    if m <= 1:
        raise ValueError("Query length must be longer than one")

    ts = ts.astype("float")
    #Add zero to the beginning of the cumsum of ts
    s = np.insert(np.cumsum(ts),0,0)
    #Add zero to the beginning of the cumsum of ts ** 2
    sSq = np.insert(np.cumsum(ts ** 2),0,0)
    segSum = s[m:] - s[:-m]
    segSumSq = sSq[m:] -sSq[:-m]

    movmean = segSum/m
    movstd = np.sqrt(segSumSq / m - (segSum/m) ** 2)

    return [movmean,movstd]

def movstd(ts,m):
    """
    Calculate the standard deviation within a moving window passing across a time series.

    Parameters
    ----------
    ts: Time series to evaluate.
    m: Width of the moving window.
    """
    if m <= 1:
        raise ValueError("Query length must be longer than one")

    ts = ts.astype("float")
    #Add zero to the beginning of the cumsum of ts
    s = np.insert(np.cumsum(ts),0,0)
    #Add zero to the beginning of the cumsum of ts ** 2
    sSq = np.insert(np.cumsum(ts ** 2),0,0)
    segSum = s[m:] - s[:-m]
    segSumSq = sSq[m:] -sSq[:-m]

    return np.sqrt(segSumSq / m - (segSum/m) ** 2)

def slidingDotProduct(query,ts,v=1): #added v
    """
    Calculate the dot product between a query and all subsequences of length(query) in the timeseries ts. Note that we use Numpy's rfft method instead of fft.

    Parameters
    ----------
    query: Specific time series query to evaluate.
    ts: Time series to calculate the query's sliding dot product against.
    v : Step size (default=1, compute every subsequence).
    """

    m = len(query)
    n = len(ts)

    if v==1:
        #if v=1 we used the previous code

        #If length is odd, zero-pad time time series
        ts_add = 0
        if n%2 ==1:
            ts = np.insert(ts,0,0)
            ts_add = 1

        q_add = 0
        #If length is odd, zero-pad query
        if m%2 == 1:
            query = np.insert(query,0,0)
            q_add = 1

        #This reverses the array
        query = query[::-1]


        query = np.pad(query,(0,n-m+ts_add-q_add),'constant')

        #Determine trim length for dot product. Note that zero-padding of the query has no effect on array length, which is solely determined by the longest vector
        trim = m-1+ts_add

        dot_product = fft.irfft(fft.rfft(ts)*fft.rfft(query))


        #Note that we only care about the dot product results from index m-1 onwards, as the first few values aren't true dot products (due to the way the FFT works for dot products)
        return dot_product[trim :]
    else: 
        #if v =/= 1
        #do not use FFT because the computational advantage is lost when v is big
        # Number of required dot products (depends on how many indexes we skip, i.e. v)
        num_dots = (n - m) // v + 1
        
        # Initialize output array
        dot_product = np.zeros(num_dots)
        
        # Compute each required dot product directly
        for i in range(num_dots):
            start = i * v #Compute only the necessary scalar products
            end = start + m
            dot_product[i] = np.dot(query, ts[start:end])
        
        return dot_product

def DotProductStomp(ts,m,dot_first,dot_prev,order):
    """
    Updates the sliding dot product for a time series ts from the previous dot product dot_prev.

    Parameters
    ----------
    ts: Time series under analysis.
    m: Length of query within sliding dot product.
    dot_first: The dot product between ts and the beginning query (QT1,1 in Zhu et.al).
    dot_prev: The dot product between ts and the query starting at index-1.
    order: The location of the first point in the query.
    """

    l = len(ts)-m+1
    dot = np.roll(dot_prev,1)

    dot += ts[order+m-1]*ts[m-1:l+m]-ts[order-1]*np.roll(ts[:l],1)

    #Update the first value in the dot product array
    dot[0] = dot_first[order]

    return dot


def mass(query,ts,v): #added v
    """
    Calculates Mueen's ultra-fast Algorithm for Similarity Search (MASS): a Euclidian distance similarity search algorithm. Note that we are returning the square of MASS.

    Parameters
    ----------
    :query: Time series snippet to evaluate. Note that the query does not have to be a subset of ts.
    :ts: Time series to compare against query.
    """

    #query_normalized = zNormalize(np.copy(query))
    m = len(query)
    q_mean = np.mean(query)
    q_std = np.std(query)
    mean, std = movmeanstd(ts,m)
    dot = slidingDotProduct(query,ts,v)

    #CONTRIBUTION
    # Ensure that the arrays used in the MASS distance calculation (dot, mean, std) have all the same length. 
    # necessary because:
    # - The sliding dot product (dot) may return fewer elements when using a step size v.
    # - The moving mean and std (mean, std) are computed over the full time series.
    # To avoid broadcasting errors or mismatched array operations, we truncate all three arrays to the minimum common length.
    # This does not result in loss of useful data, because we only retain values for which all components are available.


    min_len = min(len(dot), len(mean), len(std))
    dot = dot[:min_len]
    mean = mean[:min_len]
    std = std[:min_len]

    #res = np.sqrt(2*m*(1-(dot-m*mean*q_mean)/(m*std*q_std)))
    res = 2*m*(1-(dot-m*mean*q_mean)/(m*std*q_std))


    res_full = np.full(len(ts) - m + 1, np.nan)  # array full of NaN

    # Maps the result in the correct places (every v indexes)
    for i, val in enumerate(res):
        idx = i * v
        if idx < len(res_full):
            res_full[idx] = val

    return res_full

def massStomp(query,ts,dot_first,dot_prev,index,mean,std):
    """
    Calculates Mueen's ultra-fast Algorithm for Similarity Search (MASS) between a query and timeseries using the STOMP dot product speedup. Note that we are returning the square of MASS.

    Parameters
    ----------
    query: Time series snippet to evaluate. Note that, for STOMP, the query must be a subset of ts.
    ts: Time series to compare against query.
    dot_first: The dot product between ts and the beginning query (QT1,1 in Zhu et.al).
    dot_prev: The dot product between ts and the query starting at index-1.
    index: The location of the first point in the query.
    mean: Array containing the mean of every subsequence in ts.
    std: Array containing the standard deviation of every subsequence in ts.
    """
    m = len(query)
    dot = DotProductStomp(ts,m,dot_first,dot_prev,index)

    #Return both the MASS calcuation and the dot product
    res = 2*m*(1-(dot-m*mean[index]*mean)/(m*std[index]*std))

    return res, dot


def apply_av(mp,av=[1.0]):
    """
    Applies an annotation vector to a Matrix Profile.

    Parameters
    ----------
    mp: Tuple containing the Matrix Profile and Matrix Profile Index.
    av: Numpy array containing the annotation vector.
    """

    if len(mp[0]) != len(av):
        raise ValueError(
            "Annotation Vector must be the same length as the matrix profile")
    else:
        av_max = np.max(av)
        av_min = np.min(av)
        if av_max > 1 or av_min < 0:
            raise ValueError("Annotation Vector must be between 0 and 1")
        mp_corrected = mp[0] + (1 - np.array(av)) * np.max(mp[0])
        return (mp_corrected, mp[1])


def is_self_join(tsA, tsB):
    """
    Helper function to determine if a self join is occurring or not. When tsA 
    is absolutely equal to tsB, a self join is occurring.

    Parameters
    ----------
    tsA: Primary time series.
    tsB: Subquery time series.
    """
    return tsB is None or np.array_equal(tsA, tsB)
