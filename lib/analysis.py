import os
import pandas as pd
import numpy as np

def add_data_to_df(df, data_dict, index):
    """
    Adds the data in data_dict in the df pandas dataframe
    
    Args:
        df(`obj`): pandas dataframe
        data_dict(`dict`): dictionary with the data to be added
        index(`lst`): index of the df where the data should be added
    Returns:
        updated_df(`obj`): pandas dataframe updated with data_dict

    """
    if df.empty:
        # if the dataframe is empty, load the first set of data
        updated_df = pd.DataFrame(data_dict,
                          index=index)
    else:
        # if the dataframe has data, concatenate the new data
        updated_df = pd.concat([df, pd.DataFrame(data_dict,
                         index=index)])
    return updated_df

def analyze_time_series(path_to_datafolder):
    """
    Analyzes all time series stored in `path_to_datafolder` using the block binning method.

    Args:
        path_to_datafolder(`str`): path to the folder with the files with the time series

    Returns:
        (`obj`): pandas dataframe with

    """
    data=pd.DataFrame()
    with os.scandir(path_to_datafolder) as subdirectory:
        # Gather all data
        for subitem in subdirectory:
            if subitem.is_file():
                if 'time_series' in subitem.name:
                    # Get parameters from the file name
                    data_dict=get_params_from_dir_name(subitem.name.replace('_time_series.csv', ''))
                    # Get the observables for binning analysis
                    time_series_data=read_csv_file(path=f"{path_to_datafolder}/{subitem.name}")
                    analyzed_data=block_analyze(full_data=time_series_data)
                    value_list=[]
                    index_list=[]
                    for key in data_dict.keys():
                        value_list.append(data_dict[key])
                        index_list.append((key,"value"))
                    analyzed_data = pd.concat([pd.Series(value_list, index=index_list), analyzed_data])
                    data = add_data_to_df(df=data,
                                        data_dict=analyzed_data.to_dict(),
                                        index=[len(data)])   
    return data

def get_params_from_dir_name(name):
    """
    Gets the parameters from name assuming a structure 
    name=obsname1-value1_obsname2-value2...
    
    Args:
        name(`str`): name of the directory
    
    Returns:
        params(`dict`): dictionary with the labels and values of the parameters
    """
    entries = name.split('_')
    params = {}
    for entry in entries:
        sp_entry = entry.split('-', 1)
        params[sp_entry[0]] = sp_entry[-1]     #float(sp_entry[-1])     # creates a dictionary of parameters and their values.
    return params


def split_dataframe_in_equal_blocks(df, start_row, end_row, block_size):
    """
    Splits a Pandas dataframe in equally spaced blocks.

    Args:
        - df (`obj`): PandasDataframe
        - start_row (`int`): index of the first row
        - end_row (`int`): index of the last row
        - block_size (`int`): number of rows per block

    Returns:
        - (`list`): array of PandasDataframe of equal size
    """
    return [df[row:row+block_size] for row in range(start_row,end_row,block_size)]

def split_dataframe(df,n_blocks):
    """
    Splits a Pandas Dataframe in n_blocks of approximately the same size.

    Args:
        - df (`obj`): PandasDataframe
        - n_blocks (`int`): Number of blocks

    Returns:
        - (`list`): array of PandasDataframe 

    Notes:
        - For a `df` of length `l` that should be split into n_blocks, it returns l % n_blocks sub-arrays of size l//n_blocks + 1 and the rest of size l//n_blocks.
        - The behaviour of this function is the same as numpy.array_split for backwards compatibility, see [docs](https://numpy.org/doc/stable/reference/generated/numpy.array_split.html)

    """

    # Blocks of size 1 (s1) =  df.shape[0]//n_blocks+1

    n_blocks_s1=df.shape[0] % n_blocks
    block_size_s1=df.shape[0]//n_blocks+1
    blocks=split_dataframe_in_equal_blocks(df=df,
                                           start_row=0,
                                           end_row=n_blocks_s1*block_size_s1,
                                           block_size=block_size_s1)


    # Blocks of size 2 (s2) =  df.shape[0]//n_blocks
    block_size_s2=df.shape[0]//n_blocks
    blocks+=split_dataframe_in_equal_blocks(df=df,
                                           start_row=n_blocks_s1*block_size_s1,
                                           end_row=df.shape[0],
                                           block_size=block_size_s2)
    return blocks

def block_analyze(full_data, n_blocks=16, time_col = "time", equil=0.1,  columns_to_analyze = "all", verbose = False):
    """
    Analyzes the data in `full_data` using a binning procedure.

    Args:
        - full_data(`obj`): pandas dataframe with the observables time series
        - n_blocks(`int`): number of blocks used in the binning procedure.
        - time_col(`str`): column name where the time is stored in `full_data`. Defaults to `time`.
        - equil(`float`,opt): fraction of the data discarded as part of the equilibration. Defaults to 0.1.
        - columns_to_analyze(`list`): array of column names to be analyzed. Defaults to "all".
        - verbose(`bool`): switch to activate/deactivate printing the block size. Defaults to False.

    Returns:
        `result`: pandas dataframe with the mean (mean), statistical error (err_mean), number of effective samples (n_eff) and correlation time (tau_int) of each observable.
    """

    dt = get_dt(full_data) # check that the data was stored with the same time interval dt
    drop_rows = int(full_data.shape[0]*equil) # calculate how many rows should be dropped as equilibration
    # drop the rows that will be discarded as equlibration
    data = full_data.drop(range(0,drop_rows))
    # drop the columns step, time and MC sweep
    if time_col in data.columns :
        data = data.drop(columns = time_col)
    else:
        raise ValueError(f"could not find the time column {time_col} in the data")
    if columns_to_analyze != "all":
        for column_name in data.columns:
            if column_name not in columns_to_analyze:
                data = data.drop(columns=column_name)
    # first, do the required operations on the remaining data
    n_samples = data.shape[0] # number of samples to be analyzed
    block_size = n_samples/n_blocks # mean block size
    mean = data.mean() # calculate the mean values of each column
    var_all = data.var() # calculate the variance of each column
    if verbose:
        print(f"n_blocks b = {n_blocks},  block_size k = {block_size}")

    # calculate the mean per each block
    blocks = split_dataframe(df=data,
                             n_blocks=n_blocks)

    block_means = [] # empty list that we will use to store the means per each block
    for block in blocks:
        block_mean = block.mean() # mean values of each column within a given block
        block_means.append(block_mean)
    block_means = pd.concat(block_means, axis=1).transpose()

    # perform calculations using averages or individual data blocks
    var_blocks = (n_blocks)/(n_blocks-1)*block_means.var() # variance of the block averages = variance of the mean
    err_mean = np.sqrt(var_blocks/n_blocks) # standard error of the mean by eq.(37) of Janke
    tau_int = dt*block_size * var_blocks / var_all /2.# eq.(38) of Janke
    n_eff = n_samples / (2*tau_int/dt) # effective number of samples in the whole simulation using eq.(28) of Janke

    # concatenate the observables and atribute a key for each (unique index)
    result = pd.concat( [ mean, err_mean, n_eff, tau_int], keys= [ "mean", "err_mean", "n_eff", "tau_int" ], join="inner")
    result = pd.concat( [ pd.Series([n_blocks,block_size], index=[('n_blocks',),('block_size',)]), result])
    return result

def get_dt(data):
    """
    Sorts data to calculate the time step of the simulation.

    Args:
        - data (`obj`): pandas dataframe with the observables time series

    Returns:
        dt (`float`): simulation time step.
    """
    if 'time' in data:
        time = data['time']
    elif 'MC sweep' in data:
        time = data['MC sweep']
    else:
        raise ValueError("neither 'time' nor 'MC sweep' column found in data, got " + str(data))
    imax = data.shape[0]
    dt_init = time[1] - time[0]
    warn_lines = []
    for i in range(1,imax):
        dt = time[i] - time[i-1]
        if np.abs((dt_init - dt)/dt) > 0.01:
            warn_lines.append("Row {} dt = {} = {} - {} not equal to dt_init = {}")
    if len(warn_lines) > 20:
        print("\n")
        for line in warn_lines:
            print(line)
    return dt

def read_csv_file(path):
    """
    Reads the csv file in path.

    Args:
        - path (`str`): path to the csv file
    
    Returns:
        - `obj`: pandas dataframe with the information stored in the csv file

    """
    if os.path.exists(path):
        return pd.read_csv(filepath_or_buffer=path)
    else:
        return None

def built_output_name(input_dict):
    """
    Builts the output name for a given set of input parameters.

    Args:
        input_dict (`dict`): dictionary with all terminal inputs.

    Returns:
        output_name (`str`): name used for the output files

    Note:
        The standard formatting rule is parametername1-parametervalue1_parametername2-parametervalue2
    """
    output_name=""
    for label in input_dict:
        if type(input_dict[label]) in [str,bool]:
            formatted_variable=f"{input_dict[label]:}"
        else:
            formatted_variable=f"{input_dict[label]:.3g}"
        output_name+=f"{label}-{formatted_variable}_"
    return output_name[:-1]


