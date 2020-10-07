""" PYGEM-OGGGM COMPATIBILITY FUNCTIONS """
# External libraries
import numpy as np
import pandas as pd
import netCDF4
# Local libraries
import pygem.pygem_input as pygem_prms
from oggm import cfg, utils
from oggm import workflow
from oggm import tasks
from oggm.cfg import SEC_IN_YEAR
from oggm.core.massbalance import MassBalanceModel
from oggm.shop import rgitopo
from pygem.shop import debris, mbdata, icethickness

# Troubleshooting:
#  - EXCEPT: PASS is the key to the issues that is being experienced when running code Fabien provides on mac
#  - also have changed temporary working directories (wd), but the true problem may be the except:pass 


def single_flowline_glacier_directory_with_calving(rgi_id, reset=False, prepro_border=10, k_calving=2):
    """Prepare a GlacierDirectory for PyGEM (single flowline to start with)
    
    k_calving is free variable!
    
    Parameters
    ----------
    rgi_id : str
        the rgi id of the glacier
    reset : bool
        set to true to delete any pre-existing files. If false (the default),
        the directory won't be re-downloaded if already available locally in
        order to spare time.
    prepro_border : int
        the size of the glacier map: 10, 80, 160, 250
    Returns
    -------
    a GlacierDirectory object
    """
    if type(rgi_id) != str:
        raise ValueError('We expect rgi_id to be a string')
    if rgi_id.startswith('RGI60-') == False:
        rgi_id = 'RGI60-' + rgi_id.split('.')[0].zfill(2) + '.' + rgi_id.split('.')[1]
    else:
        raise ValueError('Check RGIId is correct')
    cfg.initialize()
    
    wd = '/Users/davidrounce/Documents/Dave_Rounce/HiMAT/Output/oggm-pygem-{}-b{}-k{}'.format(rgi_id, prepro_border, 
                                                                                              k_calving)
    cfg.PATHS['working_dir'] = wd
    
    cfg.PARAMS['use_multiple_flowlines'] = False   # why NOT multiple flowlines? 
    # -> maybe because of the glacier elevation bin approac of Rounce and Huss and Hock?!
    cfg.PARAMS['use_multiprocessing'] = False
    # Check if folder is already processed
    try:
        gdir = utils.GlacierDirectory(rgi_id)
        gdir.read_pickle('model_flowlines')
        # If the above works the directory is already processed, return
        return gdir   # why do we return here gdir,...  but then compute gdirs anyway?! 
    except:
        pass
    # If not ready, we download the preprocessed data for this glacier
    gdirs = workflow.init_glacier_regions([rgi_id],
                                          from_prepro_level=2,
                                          prepro_border=prepro_border)
    # what is the difference between gdirs and gdir????
    if not gdirs[0].is_tidewater:
        raise ValueError('This glacier is not tidewater!')
    # Compute all the stuff
    list_tasks = [
        tasks.glacier_masks,
        tasks.compute_centerlines,
        tasks.initialize_flowlines,
        tasks.compute_downstream_line,
        tasks.catchment_area,
        tasks.catchment_width_geom,
        tasks.catchment_width_correction,
        tasks.compute_downstream_bedshape,
        # Debris tasks
        debris.debris_to_gdir,
        debris.debris_binned,
        # Consensus ice thickness
        icethickness.consensus_mass_estimate,
        # Mass balance data
        mbdata.mb_bins_to_glacierwide
    ]
    for task in list_tasks:
        # The order matters!
        workflow.execute_entity_task(task, gdirs)
    
    # Calving according to Recinos et al. 2019
    #  solves equality between ice derformation and Oerleman's calving law
    #  reduces temperature sensitivity 
    from oggm.core.inversion import find_inversion_calving
    cfg.PARAMS['k_calving'] = k_calving
    df = find_inversion_calving(gdirs[0])
    print('Calving results:')
    print('k calving:', k_calving)
    for k, v in df.items():
        print(k + ':', v)
    list_tasks = [
        tasks.init_present_time_glacier,
    ]
    for task in list_tasks:
        # The order matters!
        workflow.execute_entity_task(task, gdirs)
    return gdirs[0]


def single_flowline_glacier_directory(rgi_id, reset=False, prepro_border=80):
    """Prepare a GlacierDirectory for PyGEM (single flowline to start with)

    Parameters
    ----------
    rgi_id : str
        the rgi id of the glacier (RGIv60-)
    reset : bool
        set to true to delete any pre-existing files. If false (the default),
        the directory won't be re-downloaded if already available locally in
        order to spare time.
    prepro_border : int
        the size of the glacier map: 10, 80, 160, 250

    Returns
    -------
    a GlacierDirectory object
    """


    if type(rgi_id) != str:
        raise ValueError('We expect rgi_id to be a string')
    if rgi_id.startswith('RGI60-') == False:
        rgi_id = 'RGI60-' + rgi_id.split('.')[0].zfill(2) + '.' + rgi_id.split('.')[1]
    else:
        raise ValueError('Check RGIId is correct')
#    if 'RGI60-' not in rgi_id:
#        raise ValueError('OGGM currently expects IDs to start with RGI60-')
        
#   # ----- Old initialization from February 2020-----
#    cfg.initialize()
##    wd = '/Users/davidrounce/Documents/Dave_Rounce/HiMAT/oggm-pygem-{}-b{}'.format(rgi_id, prepro_border)
##    utils.mkdir(wd, reset=reset)
##    cfg.PATHS['working_dir'] = wd
#    cfg.PATHS['working_dir'] = pygem_prms.oggm_gdir_fp
#    cfg.PARAMS['use_multiple_flowlines'] = False
#    cfg.PARAMS['use_multiprocessing'] = False
        
        
    # Initialize OGGM and set up the default run parameters
    cfg.initialize(logging_level='WORKFLOW')
    cfg.PARAMS['border'] = 10
    # Usually we recommend to set dl_verify to True - here it is quite slow
    # because of the huge files so we just turn it off.
    # Switch it on for real cases!
    cfg.PARAMS['dl_verify'] = True
    cfg.PARAMS['use_multiple_flowlines'] = False
    # temporary directory for testing (deleted on computer restart)
    #cfg.PATHS['working_dir'] = utils.get_temp_dir('PyGEM_ex') 
    cfg.PATHS['working_dir'] = pygem_prms.oggm_gdir_fp

    # Check if folder is already processed
    try:
        gdir = utils.GlacierDirectory(rgi_id)
        gdir.read_pickle('inversion_flowlines')
        # If the above works the directory is already processed, return
        return gdir
    except:
        pass

    #%%
    
    # ===== SELECT BEST DEM =====
    # Get the pre-processed topography data
    gdirs = rgitopo.init_glacier_directories_from_rgitopo([rgi_id])
    
    gdirs = workflow.init_glacier_directories([rgi_id])
#    # If not ready, we download the preprocessed data for this glacier
#    gdirs = workflow.init_glacier_regions([rgi_id],
#                                          from_prepro_level=2,
#                                          prepro_border=prepro_border)

    # Compute all the stuff
    list_tasks = [
        tasks.glacier_masks,
        tasks.compute_centerlines,
        tasks.initialize_flowlines,
        tasks.compute_downstream_line,
        tasks.catchment_area,
        tasks.catchment_width_geom,
        tasks.catchment_width_correction,
    #    tasks.compute_downstream_bedshape,
        # Debris tasks
        debris.debris_to_gdir,
        debris.debris_binned,
        # Consensus ice thickness
        icethickness.consensus_mass_estimate,
        # Mass balance data
        mbdata.mb_bins_to_glacierwide
    #    tasks.local_t_star,
    #    tasks.mu_star_calibration,
    #    tasks.prepare_for_inversion,
    #    tasks.mass_conservation_inversion,
    #    tasks.filter_inversion_output,
    #    tasks.init_present_time_glacier,
    ]
    
    for task in list_tasks:
        workflow.execute_entity_task(task, gdirs)

    return gdirs[0]


def get_glacier_zwh(gdir):
    """Computes this glaciers altitude, width and ice thickness.

    Parameters
    ----------
    gdir : GlacierDirectory
        the glacier to compute

    Returns
    -------
    a dataframe with the requested data
    """

    fls = gdir.read_pickle('model_flowlines')
    z = np.array([])
    w = np.array([])
    h = np.array([])
    for fl in fls:
        # Widths (in m)
        w = np.append(w, fl.widths_m)
        # Altitude (in m)
        z = np.append(z, fl.surface_h)
        # Ice thickness (in m)
        h = np.append(h, fl.thick)
    # Distance between two points
    dx = fl.dx_meter

    # Output
    df = pd.DataFrame()
    df['z'] = z
    df['w'] = w
    df['h'] = h
    df['dx'] = dx

    return df


class RandomLinearMassBalance(MassBalanceModel):
    """Mass-balance as a linear function of altitude with random ELA.

    This is a dummy MB model to illustrate how to program one.

    The reference ELA is taken at a percentile altitude of the glacier.
    It then varies randomly from year to year.

    This class implements the MassBalanceModel interface so that the
    dynamical model can use it. Even if you are not familiar with object
    oriented programming, I hope that the example below is simple enough.
    """

    def __init__(self, gdir, grad=3., h_perc=60, sigma_ela=100., seed=None):
        """ Initialize.

        Parameters
        ----------
        gdir : oggm.GlacierDirectory
            the working glacier directory
        grad: float
            Mass-balance gradient (unit: [mm w.e. yr-1 m-1])
        h_perc: int
            The percentile of the glacier elevation to choose the ELA
        sigma_ela: float
            The standard deviation of the ELA (unit: [m])
        seed : int, optional
            Random seed used to initialize the pseudo-random number generator.

        """
        super(RandomLinearMassBalance, self).__init__()
        self.valid_bounds = [-1e4, 2e4]  # in m
        self.grad = grad
        self.sigma_ela = sigma_ela
        self.hemisphere = 'nh'
        self.rng = np.random.RandomState(seed)

        # Decide on a reference ELA
        grids_file = gdir.get_filepath('gridded_data')
        with netCDF4.Dataset(grids_file) as nc:
            glacier_mask = nc.variables['glacier_mask'][:]
            glacier_topo = nc.variables['topo_smoothed'][:]

        self.orig_ela_h = np.percentile(glacier_topo[glacier_mask == 1],
                                        h_perc)
        self.ela_h_per_year = dict()  # empty dictionary

    def get_random_ela_h(self, year):
        """This generates a random ELA for the requested year.

        Since we do not know which years are going to be asked for we generate
        them on the go.
        """

        year = int(year)
        if year in self.ela_h_per_year:
            # If already computed, nothing to be done
            return self.ela_h_per_year[year]

        # Else we generate it for this year
        ela_h = self.orig_ela_h + self.rng.randn() * self.sigma_ela
        self.ela_h_per_year[year] = ela_h
        return ela_h

    def get_annual_mb(self, heights, year=None, fl_id=None):

        # Compute the mass-balance gradient
        ela_h = self.get_random_ela_h(year)
        mb = (np.asarray(heights) - ela_h) * self.grad

        # Convert to units of [m s-1] (meters of ice per second)
        return mb / SEC_IN_YEAR / cfg.PARAMS['ice_density']
    

