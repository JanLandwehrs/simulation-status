#!/usr/bin/env python3
import datetime
import logging
import matplotlib.pyplot as plt
import natsort as ns
import numpy as np
import pandas as pd
import re
import seaborn as sns

from funs import *
from pyesgf.search import SearchConnection

loglevel = logging.INFO
logger = logging.getLogger('root')
logger.setLevel(loglevel)
loghandler = logging.StreamHandler()
loghandler.setFormatter(logging.Formatter('[%(asctime)s] %(message)s'))
logger.addHandler(loghandler)

facets = (
  'project', 'activity', 'domain', 'institution', 'driving_model', 'experiment', 'ensemble',
  'model', 'model_version', 'frequency', 'variable', 'version'
)

def version_range_string(vstring):
  vint = int(vstring[1:])
  return('minVersionDate=%d&maxVersionDate=%d' % (vint, vint))

#
#   Load search results
#
conn = SearchConnection('http://esgf-data.dkrz.de/esg-search', distrib=True)
#conn = SearchConnection('https://esgf-node.ipsl.upmc.fr/esg-search', distrib=True)
logging.getLogger('pyesgf.search.connection').setLevel(loglevel)
dflist = []
for proj in ['CORDEX-FPSCONV']:
  logger.info(f'Retrieving {proj} variables ...')
  ctx = conn.new_context(project = proj)
  dids = [result.dataset_id for result in ctx.search(batch_size=1000, ignore_facet_check=True)]
  datanode_part = re.compile('\|.*$')
  dataset_ids = [datanode_part.sub('', did).split('.') for did in dids]
  dflist.append(pd.DataFrame(dataset_ids))
df = pd.concat(dflist)
df.columns = facets

# Add ESGF search URL
search_urls = []
for idx, row in df.iterrows():
  row_dict = row.to_dict()
  search_urls.append(
    'https://esgf-metagrid.cloud.dkrz.de/search?project=CORDEX&'
#      + version_range_string(row_dict['version']) + '&'
      + 'activeFacets=%7B%22project%22%3A%22CORDEX-FPSCONV%22%2C%22experiment%22%3A%22{experiment}%22%2C%22driving_model%22%3A%22{driving_model}%22%2C%22institute%22%3A%22{institution}%22%2C%22domain%22%3A%22{domain}%22%2C%22ensemble%22%3A%22{ensemble}%22%2C%22rcm_name%22%3A%22{model}%22%2C%22rcm_version%22%3A%22{model_version}%22%2C%22time_frequency%22%3A%22{frequency}%22%2C%22variable%22%3A%22{variable}%22%7D'.format_map(row_dict)
  )
df['search_url'] = search_urls

df.to_csv('docs/CORDEX_FPSCONV_ESGF_all_variables.csv', index = False)

# Drop unnecessary columns
df.drop(columns = ['project', 'activity', 'version'], inplace = True)
df.drop_duplicates(inplace = True)
df.sort_values(['domain', 'institution', 'model', 'model_version', 'driving_model', 'ensemble', 'experiment'], inplace = True)

#
#  Plot variable availability as heatmap
#
data = pd.read_csv('docs/CORDEX_FPSCONV_ESGF_all_variables.csv', usecols=['variable', 'frequency', 'model'])
# Avoid showing different subdaily frequencies
data['frequency'] = data['frequency'].replace('.hr', 'xhr', regex = True)
data.drop_duplicates(inplace = True)
# matrix with models as rows and variables as columns
matrix = data.pivot_table(index='model', columns=['frequency', 'variable'], aggfunc='size', fill_value=0)
matrix = matrix.replace(0, np.nan)
# Plot as heatmap (make sure to show all ticks and labels)
plt.figure(figsize=(30,20))
ax = sns.heatmap(matrix, cmap='YlGnBu_r', annot=False, cbar=False, linewidths=1, linecolor='lightgray')
ax.set_xticks(0.5+np.arange(len(matrix.columns)))
xticklabels = [f'{v} ({f})' for f,v in matrix.columns]
xticklabels = (pd.Series(xticklabels)
  .replace(r'(.*) \(fx\)', r'\1 (fx)   ', regex=True)
  .replace(r'(.*) \(xhr\)', r'\1 (xhr)  ', regex=True)
).to_list()
ax.set_xticklabels(xticklabels)
ax.set_xlabel("variable (freq.)")
ax.set_yticks(0.5+np.arange(len(matrix.index)))
ax.set_yticklabels(matrix.index, rotation=0)
ax.set_aspect('equal')
plt.savefig('docs/CORDEX_FPSCONV_varlist.png', bbox_inches='tight')

#
#  Simulation and variable list as interactive datatable
#
collapse_institutions = True
domains = sorted(list(set(df.domain)))
df = df.assign(status='published') # These are only ESGF published data
df.to_csv('docs/CORDEX_FPSCONV_status.csv', index = False)
csv2datatable(
  'docs/CORDEX_FPSCONV_status.csv',
  'docs/CORDEX_FPSCONV_varlist.html',
  column_as_link = 'variable',
  column_as_link_source = 'search_url',
  title = 'CORDEX-FPSCONV on ESGF',
  intro = f'''
<p> CORDEX-FPSCONV simulations providing some data on ESGF as of <b>{datetime.datetime.now().strftime("%Y-%m-%d %H:%M")}</b>. The full list as CSV can be obtained from <a href="https://github.com/WCRP-CORDEX/simulation-status/raw/main/docs/CORDEX_FPSCONV_ESGF_all_variables.csv">here</a>.
<p> The graphical summary below provides just an overview of the existing data. The variables shown could be available only for a particular experiment (e.g. only for evaluation and not for the scenarios). All subdaily output (1hr, 3hr and 6hr) has been collapsed into a single entry marked as 'xhr'. Use the search box below to find the actual variables and frecuencies available for a given experiment. E.g. try to enter "hr rcp ta500". Variables names in the interactive data table below link to the ESGF, where you can download the corresponding data files.
<p>
<img src="CORDEX_FPSCONV_varlist.png"/>
'''
)

#
#  GCM-RCM matrix
#
f = open(f'docs/CORDEX_FPSCONV_status.html','w')
f.write(f'''<!DOCTYPE html>
<html><head>
<style>
body {{ padding-bottom: 600px; }}
tr:hover {{background-color:#f5f5f5;}}
th, td {{text-align: center; padding: 3px;}}
h2 {{text-align: center;}}
table {{border-collapse: collapse;}}
span.planned {{color: #FF9999}}
span.running {{color: #009900}}
span.completed {{color: black; font-weight: bold}}
span.published {{color: #3399FF; font-weight: bold}}
a {{color: DodgerBlue}}
a:link {{ text-decoration: none; }}
a:visited {{ text-decoration: none; }}
a:hover {{ text-decoration: underline; }}
a:active {{ text-decoration: underline;}}
</style>
</head><body>
<h1 id="top"> CORDEX-FPSCONV ESGF summary tables</h1>
<p style="text-align: right;">(Version: {datetime.datetime.now().strftime("%Y-%m-%d %H:%M")})</p>
<p style="text-align:left"> Domains:</p>
<ul>
''')
dom_prefixes = sorted(list(set([x[0:3] for x in domains])))
for domp in dom_prefixes:
  f.write('  <li>')
  f.write(' · '.join([f'<a href="#{x}">{x}</a>' for x in domains if x.startswith(domp)]))
  f.write('  </li>\n')
f.write('</ul>')
d1 = dict(selector=".level0", props=[('min-width', '100px')])
for domain in domains:
  f.write(f'''<h2 id="{domain}">{domain}<a href="#top">^</a></h2>''')
  dom_df = df[df.domain == domain]
  dom_df = dom_df.drop(columns=['frequency', 'variable', 'search_url']).drop_duplicates()
  if dom_df.empty:
    continue
  dom_df = dom_df.assign(htmlstatus=pd.Series('<span class="' + dom_df.status + '">' + dom_df.experiment + '</span>', index=dom_df.index))
  dom_df = dom_df.assign(instmodel=pd.Series(dom_df.institution + '-' + dom_df.model, index=dom_df.index))
  column_id = 'model' if collapse_institutions else 'instmodel'
  dom_df_matrix = dom_df.pivot_table(
    index = ('driving_model', 'ensemble'),
    columns = column_id,
    values = 'htmlstatus',
    aggfunc = lambda x: ' '.join(x.dropna())
  )
  dom_df_matrix = pd.concat([  # Bring ERAIN to the top
    dom_df_matrix.query("driving_model == 'ECMWF-ERAINT'"),
    dom_df_matrix.drop(('ECMWF-ERAINT','r1i1p1'), axis=0, errors='ignore')
  ], axis=0)
  if collapse_institutions:
    inst = dom_df.drop_duplicates(subset=['institution','model']).pivot_table(
      index = ('driving_model', 'ensemble'),
      columns = 'model',
      values = 'institution',
      aggfunc = lambda x: ', '.join(x.dropna())
    ).agg(lambda x: ', '.join(x.dropna()))
    inst.name = ('','Institutes')
    dom_df_matrix = pd.concat([dom_df_matrix, inst.to_frame().T])
    inst_index = dom_df_matrix.loc[inst.name]
    dom_df_matrix = dom_df_matrix.drop(inst.name)
    dom_df_matrix.columns = pd.MultiIndex.from_tuples([(inst_index[col].values[0], col) for col in dom_df_matrix.columns])
    dom_df_matrix.columns.names = ['Institution(s)','RCM']
  # Drop evaluation runs and r0 members (coming from static variables)
  #dom_df_matrix.drop('ECMWF-ERAINT', level=0, axis=0, inplace=True, errors='ignore')
  dom_df_matrix.drop('r0i0p0', level=1, axis=0, inplace=True, errors='ignore')
  f.write(f'''<p style="font-size: smaller;"> Colour legend:
      <span class="planned">planned</span>
      <span class="running">running</span>
      <span class="completed">completed</span>
      <span class="published">published</span>
    </p>
  ''')
  f.write(dom_df_matrix.style
     .set_properties(**{'font-size':'8pt', 'border':'1px lightgrey solid !important'})
     .set_table_styles([d1,{
        'selector': 'th',
        'props': [('font-size', '8pt'),('border-style','solid'),('border-width','1px')]
      }])
     .to_html()
     .replace('nan','')
     .replace('historical','hist')
  )
f.write('</body></html>')
f.close()


