# NASA Space Apps | Field Shift | Madinah crop suitability prototype
# Run this entire file in one Google Colab cell using %run, or paste its contents.
import sys, subprocess, os, math, calendar
from pathlib import Path
subprocess.check_call([sys.executable, '-m', 'pip', 'install', '-q', 'pyarrow', 'openpyxl', 'xarray', 'cartopy'])
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from IPython.display import display
from google.colab import files

# 1. Data acquisition
ROOT = Path('/content')
MODEL = ROOT / 'ecocrop'
if not (MODEL / 'ecocrop_utils.py').exists():
    subprocess.check_call(['git', 'clone', 'https://github.com/OpenCLIM/ecocrop.git', str(MODEL)])
sys.path.insert(0, str(MODEL))
import ecocrop_utils as eco
crop_url = 'https://digital-atlas.s3.amazonaws.com/cdh/data/ecocrop/ecocrop.parquet'
df = pd.read_parquet(crop_url).reset_index(drop=True)
path = ROOT / 'MEDINA_NASA_DATA.xlsx'
if not path.exists():
    uploaded = files.upload()
    if path.name not in uploaded:
        raise ValueError('Upload MEDINA_NASA_DATA.xlsx')
    path.write_bytes(uploaded[path.name])
months = 'JAN FEB MAR APR MAY JUN JUL AUG SEP OCT NOV DEC'.split()
nasa = pd.read_excel(path)
w = nasa.melt(id_vars=['PARAMETER','YEAR'], value_vars=months, var_name='month', value_name='value')
w['month'] = w['month'].map(dict(zip(months, range(1,13))))
w['date'] = pd.to_datetime(dict(year=w.YEAR, month=w.month, day=1))
w['value'] = pd.to_numeric(w.value, errors='coerce').replace(-999, np.nan)
weather_df = w.pivot(index='date', columns='PARAMETER', values='value').sort_index()
weather_df = weather_df.reindex(pd.date_range('2020-01-01','2025-12-01',freq='MS'))
weather_df.index.name = 'date'
assert weather_df.shape == (72,12), weather_df.shape
assert weather_df['T2M'].notna().all(), 'Missing monthly temperature'
weather_df['rain_mm_month'] = weather_df['IMERG_PRECTOT'] * weather_df.index.days_in_month
print('Crop records:', len(df), '| Climate months:', len(weather_df))
print('Missing climate values:'); display(weather_df.isna().sum())

# 2. SoilGrids snapshot, sampled at 24.40 N, 39.60 E.
# NASA climate point is 24.4694 N, 39.6053 E; not identical to soil point.
# Values below are already converted from the original SoilGrids integer units.
soil_clean = pd.DataFrame({
    'depth':['0-5cm','5-15cm','15-30cm','30-60cm','60-100cm','100-200cm'],
    'phh2o':[8.1,8.1,8.1,8.0,8.0,8.0],
    'sand':[47.7,47.2,48.3,47.5,48.6,48.8],
    'clay':[18.7,19.8,18.5,18.3,18.2,16.6],
    'silt':[33.6,33.0,33.2,34.2,33.2,34.6],
    'soc_g_kg':[3.5,3.1,2.1,1.4,1.1,1.1]}) .set_index('depth')
soil_ph = float(np.average(soil_clean.phh2o.iloc[:3], weights=[5,10,15]))
soil_texture = 'medium' # Loam, mapped to ECOCROP medium class
print('Soil profile:'); display(soil_clean)

# 3. Scoring functions
# Temperature and rainfall: OpenCLIM. pH and texture: prototype extensions.
def labels(v):
    if isinstance(v,(list,tuple,np.ndarray)): return [str(x).strip().lower() for x in v]
    return [] if pd.isna(v) else [str(v).strip().lower()]

def thresholds(c, names):
    a = pd.to_numeric(pd.Series([c[n] for n in names]), errors='coerce').to_numpy(float)
    return a if np.isfinite(a).all() and np.all(np.diff(a)>=0) else None

def trapezoid(x,a):
    lo,oplo,ophi,hi = a
    if not np.isfinite(x): return np.nan
    if x<lo or x>hi: return 0.
    if oplo<=x<=ophi: return 100.
    if x<oplo: return 100*(x-lo)/(oplo-lo)
    return 100*(hi-x)/(hi-ophi)

def evaluate_temperature(c, temperatures):
    a=thresholds(c,['tmin','topmn','topmx','tmax'])
    if a is None: return None
    lo,oplo,ophi,hi=a.astype(np.float32)
    # Equal endpoints can cause division by zero in the upstream implementation.
    if lo==oplo or ophi==hi:
        return np.array([trapezoid(x,a) for x in temperatures])
    return np.asarray(eco.score_temp2(np.asarray(temperatures,dtype=np.float32),lo,hi,oplo,ophi),dtype=np.float32)*100

def evaluate_ph(c):
    a=thresholds(c,['phmin','phopmn','phopmx','phmax'])
    return np.nan if a is None else trapezoid(soil_ph,a)

def evaluate_texture(c):
    optimal,acceptable=labels(c['text']),labels(c['textr'])
    if soil_texture in optimal or 'wide' in optimal: return 100.
    if soil_texture in acceptable or 'wide' in acceptable: return 50.
    return 0. if acceptable else np.nan

def evaluate_rainfall(c,annual_rain):
    a=thresholds(c,['rmin','ropmn','ropmx','rmax'])
    if a is None or not np.isfinite(annual_rain): return np.nan
    lo,oplo,ophi,hi=a.astype(np.float32)
    peak=(oplo+ophi)/2
    if peak==lo or peak==hi: return trapezoid(annual_rain,[lo,peak,peak,hi])
    return float(np.asarray(eco.score_prec2(np.array([annual_rain],dtype=np.float32),lo,hi,oplo,ophi))[0])

# 4. Historical growing windows and crop ranking
# Monthly mean temperature; extreme temperatures are reported separately.
# Irrigation assumed available; annual rainfall score is diagnostic only.
annual_rain=weather_df.rain_mm_month.groupby(weather_df.index.year).sum(min_count=12)
results=[]
for idx,c in df.iterrows():
    life=labels(c['lispa'])
    kind='Perennial' if 'perennial' in life else ('Seasonal' if set(life)&{'annual','biennial'} else 'Unknown')
    ph,texture=evaluate_ph(c),evaluate_texture(c)
    soil=min(ph,texture) if np.isfinite([ph,texture]).all() else np.nan
    temp=evaluate_temperature(c,weather_df.T2M.values)
    best_month=duration=temp_score=history=extreme_fraction=np.nan
    n_windows=0
    status='Evaluated'
    if temp is None: status='Missing or invalid temperature requirements'
    elif kind=='Unknown': status='Unknown life cycle'
    else:
        s=pd.Series(temp,index=weather_df.index)
        a=thresholds(c,['tmin','topmn','topmx','tmax'])
        extremes=(weather_df.T2M_MIN<a[0]) | (weather_df.T2M_MAX>a[3])
        if kind=='Perennial':
            windows=s.groupby(s.index.year).min()
            extreme_fraction=float(extremes.mean())
        else:
            gmin,gmax=c['gmin'],c['gmax']
            if pd.isna(gmin) or pd.isna(gmax) or not 0<gmin<=gmax or gmin>365.28:
                windows=pd.Series(dtype=float); status='Unsupported growing duration'
            else:
                duration=math.ceil(gmin/30.44)
                rolling=s.rolling(duration,min_periods=duration).min().shift(1-duration)
                monthly=rolling.groupby(rolling.index.month).mean().dropna()
                if monthly.empty: windows=pd.Series(dtype=float)
                else:
                    best_month=int(monthly.idxmax())
                    windows=rolling[rolling.index.month==best_month].dropna()
                    flags=extremes.astype(float).rolling(duration,min_periods=duration).max().shift(1-duration)
                    extreme_fraction=float(flags.loc[windows.index].mean())
        if len(windows):
            temp_score=float(windows.mean()); n_windows=len(windows)
            history=float((windows>=50).mean()*100) # descriptive threshold, not probability
        elif status=='Evaluated': status='No complete growing window'
    final=min(temp_score,soil) if np.isfinite([temp_score,soil]).all() else np.nan
    if status=='Evaluated' and not np.isfinite(soil): status='Insufficient soil requirements'
    rain_scores=[evaluate_rainfall(c,v) for v in annual_rain]
    rain_score=float(np.nanmean(rain_scores)) if np.isfinite(rain_scores).any() else np.nan
    results.append(dict(crop_id=idx,scientificname=c['scientificname'],comname='; '.join(labels(c['comname'])),category='; '.join(labels(c['cat'])),crop_type=kind,ph_score=ph,texture_score=texture,soil_score=soil,best_month=best_month,best_planting_month=calendar.month_name[int(best_month)] if np.isfinite(best_month) else '',growing_months=duration,temperature_score=temp_score,final_score=final,historical_compatibility_pct=history,complete_windows=n_windows,extreme_window_fraction=extreme_fraction,rainfed_annual_score=rain_score,status=status))
ranking_df=pd.DataFrame(results).sort_values('final_score',ascending=False,na_position='last')
# Local novelty is not verified; absence of records is not evidence of absence.
ranking_df['local_cultivation_status']='Not verified'
for name in ['Cicer arietinum','Chenopodium quinoa','Cyamopsis tetragonoloba']:
    ranking_df.loc[ranking_df.scientificname.eq(name),'local_cultivation_status']='Candidate for local record verification'

# 5. Results and visualizations
cols=['scientificname','comname','final_score','temperature_score','soil_score','best_planting_month','growing_months','historical_compatibility_pct','extreme_window_fraction','rainfed_annual_score']
print('Total database:',len(ranking_df),'| Scored:',ranking_df.final_score.notna().sum(),'| Positive:',ranking_df.final_score.gt(0).sum())
for kind in ['Seasonal','Perennial']:
    top=ranking_df.loc[(ranking_df.crop_type==kind)&ranking_df.final_score.gt(0)].head(20)
    print('\nTop',kind,'crops'); display(top[cols].round(2))
    if len(top):
        ax=top.head(10).sort_values('final_score').plot.barh(x='scientificname',y='final_score',legend=False,figsize=(9,5))
        ax.set(xlim=(0,100),xlabel='Prototype suitability score (0–100)',ylabel='',title=f'Top {kind} candidates — Madinah')
        plt.tight_layout(); plt.show()
print('Known crops / candidate checks:')
display(ranking_df[ranking_df.scientificname.str.contains('Cicer arietinum|Chenopodium quinoa|Cyamopsis tetragonoloba|Phoenix dactylifera|Hordeum vulgare|Triticum aestivum',regex=True,na=False)][cols].round(2))
weather_df.groupby(weather_df.index.month)[['T2M','T2M_MIN','T2M_MAX']].mean().plot(figsize=(10,4),title='Monthly temperature climatology (2020–2025)'); plt.ylabel('°C'); plt.xlabel('Month'); plt.show()

# 6. Export reproducible outputs
out=ROOT/'medina_results'; out.mkdir(exist_ok=True)
ranking_df.to_csv(out/'medina_crop_ranking.csv',index=False)
weather_df.to_csv(out/'medina_climate_monthly.csv')
soil_clean.to_csv(out/'soil_data_clean.csv')
ranking_df[ranking_df.crop_type.eq('Seasonal')].to_csv(out/'seasonal_ranking.csv',index=False)
ranking_df[ranking_df.crop_type.eq('Perennial')].to_csv(out/'perennial_ranking.csv',index=False)
import shutil
archive=shutil.make_archive(str(ROOT/'medina_results'),'zip',out)
print('Saved:',archive)
print('Limitations: monthly means; assumed irrigation; no yield prediction; no salinity, verified local inventory or validated rotation module. Scores are not probabilities. Extreme-temperature flags are diagnostic only.')
# Uncomment to download results automatically:
# files.download(archive)
