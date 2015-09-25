from flask import Flask,render_template, request, redirect, url_for, send_from_directory

app = Flask('modelinspector')
app.debug = True

import IPython
import tempfile
import os
import shutil
import subprocess
import glob
import yaml
import time

@app.route('/')
def submit():
  return render_template('submit.html')
  
@app.route('/submission',methods = ['POST'])
def submission():
  tmpdir = tempfile.mkdtemp(dir='uploads/')
  for d in ['config','data','results']:
    os.makedirs('{}/{}'.format(tmpdir,d))
  shutil.copy('{}/etc/HistFactorySchema.dtd'.format(os.environ['ROOTSYS']),
              '{}/config/HistFactorySchema.dtd'.format(tmpdir))

  for name,f in request.files.iteritems():
    if f:
      print "saving "+f.name
      subdir = ''
      if 'XML' in f.name: subdir='config'
      if 'ROOT' in f.name: subdir='data'
      f.save('{}/{}/{}'.format(tmpdir,subdir,f.filename if not f.name=='XMLFile1' else 'toplvl.xml'))

  subprocess.check_call(['hist2workspace','config/{}'.format('toplvl.xml')],cwd = tmpdir)

  subprocess.check_call([os.path.abspath('./plot.py'),'dump_information',
                         './config/toplvl.xml',
                         './histfactory_info.yaml'],
                         cwd = tmpdir)

  return redirect(url_for('inspect',id = os.path.basename(tmpdir)))
  
@app.route('/inspect/<id>')
def inspect(id):
  workspace = 'combined'
  tmpdir = 'uploads/{}'.format(id)
  info = yaml.load(open('{}/histfactory_info.yaml'.format(tmpdir)))
  
  measurement = info['Combination']['Measurements'][0]['name']

  tmpdir = 'uploads/{}'.format(id)
  rootfile = '{}/{}_{}_{}_model.root'.format(tmpdir,info['Combination']['Prefix'],workspace,measurement)
  vardefpath = '{}/vardef_{}.yaml'.format(tmpdir,measurement)

  plotted =[os.path.basename(x).split('.')[0].split('_')[-1] for x in glob.glob('{}/*.png'.format(tmpdir))]

  plots = ['/plotfile/{}/{}?{}'.format(id,channel,time.time()) for channel in plotted]
  parpointpath = '{}/parpoint.yaml'.format(tmpdir)

  if not os.path.exists(vardefpath):
    subprocess.check_call(['./plot.py','write_vardef',rootfile,workspace,vardefpath])
  
  parvals = None
  if os.path.exists(parpointpath):
     parvals = yaml.load(open(parpointpath))
  
  vardef = yaml.load(open(vardefpath))
  return render_template('inspect.html',
                          vardef = vardef,
                          plots = plots ,
                          id = id,
                          parvals = parvals,
                          histfactory_info = yaml.load(open('{}/histfactory_info.yaml'.format(tmpdir))))


@app.route('/fit/<id>',methods = ['POST'])
def fit(id):
  workspace = 'combined'
  tmpdir = 'uploads/{}'.format(id)
  info = yaml.load(open('{}/histfactory_info.yaml'.format(tmpdir)))
  parvals = {}
  measurement = info['Combination']['Measurements'][0]['name']
  
  
  tmpdir = 'uploads/{}'.format(id)
  rootfile = '{}/{}_{}_{}_model.root'.format(tmpdir,info['Combination']['Prefix'],workspace,measurement)
  parpointpath = '{}/parpoint.yaml'.format(tmpdir)

  subprocess.check_call(['./plot.py','fit',
                         rootfile,
                         workspace,
                         parpointpath])
  return redirect(url_for('inspect',id = id))


@app.route('/plot/<id>',methods = ['POST'])
def plot(id):
  workspace = 'combined'
  observable = 'x'
  tmpdir = 'uploads/{}'.format(id)
  info = yaml.load(open('{}/histfactory_info.yaml'.format(tmpdir)))

  channels = [request.form[x] for x in request.form.keys() if x.startswith('channel-')]
  channels_with_samples = {c:[request.form[x] for x in request.form.keys() if x.startswith('sample_{}'.format(c))] for c in channels}

  parvals = {}
  measurement = info['Combination']['Measurements'][0]['name']

  rootfile = '{}/{}_{}_{}_model.root'.format(tmpdir,info['Combination']['Prefix'],workspace,measurement)
  vardefpath = '{}/vardef_{}.yaml'.format(tmpdir,measurement)
  parpointpath = '{}/parpoint.yaml'.format(tmpdir)

  vardef = yaml.load(open('{}/vardef_{}.yaml'.format(tmpdir,measurement)))

  if request.method == 'POST':

    parvals = {k.replace('par-',''):float(v) for k,v in request.form.iteritems() if k.startswith('par-')}
    with open(parpointpath,'w') as parpoint:
      parpoint.write(yaml.safe_dump(parvals,default_flow_style=False))
  else:
    parvals = yaml.load(open(parpointpath.format(tmpdir)))

  for channel,samples in channels_with_samples.iteritems():
    plotpath = '{}/plot_{}.png'.format(tmpdir,channel)
    subprocess.check_call(['./plot.py','plot_channel',
                           rootfile,
                           workspace,
                           channel,
                           observable,
                           ','.join(reversed(samples)),
                           parpointpath,
                           '-o',plotpath])

  return redirect(url_for('inspect',id = id))
  
@app.route('/plotfile/<id>/<channel>')
def plotfile(id,channel):
  tmpdir = 'uploads/{}'.format(id)
  return send_from_directory(tmpdir,'plot_{}.png'.format(channel))
  
  
if __name__ == '__main__':
  app.run()