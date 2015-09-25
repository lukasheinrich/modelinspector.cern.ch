#!/usr/bin/env python

import ROOT
ROOT.gROOT.SetBatch(True)
import yaml
import IPython
import click
import os
from lxml import etree

@click.group()
def toplevel():
  pass


def get_funcname(funcs,component,channel):
  it = funcs.iterator()
  funcname = None
  for i in range(funcs.getSize()):
    v = it.Next()
    print v.GetName()
    if v.GetName().startswith('L_x_{}_{}'.format(component,channel)):
      funcname = v.GetName()
      return funcname
  return funcname
  
def get_datahist(data,obsvar,channel):
  reduced = data.reduce('channelCat == channelCat::{}'.format(channel))
  varlist = ROOT.RooArgList()
  varlist.add(obsvar)
  datahist =obsvar.createHistogram('data_{}'.format(channel))
  datahist = reduced.fillHistogram(datahist,varlist)
  datahist.Sumw2(0)
  datahist.SetMarkerStyle(20);
  datahist.SetLineColor(ROOT.kBlack)
  return datahist

def plot(ws,channel,obs,components,filename):
  obsname='obs_{}_{}'.format(obs,channel)
  obs = ws.var(obsname)


  frame = obs.frame()

  data = ws.data('obsData')
  reduced = data.reduce('channelCat == channelCat::{}'.format(channel))

  funcs = ws.allFunctions()

  stack = ROOT.THStack()
  colors = [ROOT.kRed,ROOT.kBlue,ROOT.kGreen,ROOT.kMagenta]
  for color,component in zip(colors,components):
    funcname=get_funcname(funcs,component,channel)

    function = ws.function(funcname)
    histogram = function.createHistogram(obsname)
    histogram.SetFillColor(color)
    stack.Add(histogram)
    print 'LUKE: {}'.format(component)

  c = ROOT.TCanvas()
  datahist = get_datahist(data,obs,channel)

  frame = datahist.Clone()
  frame.Reset('ICE')
  frame.SetTitle(channel)
  frame.GetYaxis().SetRangeUser(0,datahist.GetMaximum()*1.5)
  frame.Draw()
  
  
  stack.Draw('histsame')
  datahist.Draw('sameE0')
  c.SaveAs(filename)
  
  
def save_pars(ws,output,justvalues = False):
  mc = ws.obj('ModelConfig')
  it = mc.GetNuisanceParameters().iterator()
  v = it.Next()
  parpoint = {}


  def write(v):
    if justvalues:
      parpoint[v.GetName()] = v.getVal()
    else:
      parpoint[v.GetName()] = {'min':v.getMin(),'max':v.getMax(),'defval':v.getVal()}
    
  while v:
    write(v)
    v = it.Next()


  v = mc.GetParametersOfInterest().iterator().Next()
  print "POI: {}".format(v)
  write(v)

  with open(output,'w') as results:
    results.write(yaml.dump(parpoint,default_flow_style = False))
  
  
@toplevel.command()
@click.argument('rootfile')
@click.argument('workspace')
@click.argument('output')
def write_vardef(rootfile,workspace,output):
  f = ROOT.TFile.Open(rootfile)
  ws = f.Get(workspace)
  save_pars(ws,output)


@toplevel.command()
@click.argument('rootfile')
@click.argument('workspace')
@click.argument('output')
def fit(rootfile,workspace,output):
  f = ROOT.TFile.Open(rootfile)
  ws = f.Get(workspace)
  ws.pdf('simPdf').fitTo(ws.data('obsData'),
    ROOT.RooFit.Extended(True),
    ROOT.RooFit.Save(True),
    ROOT.RooFit.Minimizer("Minuit","Migrad"),
    ROOT.RooFit.Offset(True)
  )
  save_pars(ws,output,True)


def get_path(basedir,relpath):
  return '{}/{}'.format(basedir,relpath.split('./',1)[-1])


def parse_histfactory_xml(toplvlxml):
  dirname = os.path.abspath(os.path.dirname(toplvlxml))
  histfithome = dirname.split('/config')[0]
  
  p = etree.parse(toplvlxml)
  channels =  [etree.parse(open(get_path(histfithome,inpt.text))).xpath('/Channel')[0] for inpt in p.xpath('Input')]

  parsed_data = {
    'Combination':{
      'Prefix':p.xpath('/Combination')[0].attrib['OutputFilePrefix'].split('./',1)[-1],
      'Measurements':[ {'name':x.attrib['Name'] for x in p.xpath('Measurement')}]
    }
  }

  channel_info = []
  for input_tag in p.xpath('Input'):
    channel_xml = etree.parse(open(get_path(histfithome,input_tag.text)))
    channel_name = channel_xml.xpath('/Channel')[0].attrib['Name']
    sample_names = [x.attrib['Name'] for x in channel_xml.xpath('Sample')]
    channel_info += [{'name':channel_name,'samples':sample_names}]

  parsed_data['Combination']['Inputs'] = channel_info
  return parsed_data
  
@toplevel.command()
@click.argument('toplvlxml')
@click.argument('output')
def dump_information(toplvlxml,output):
  parsed_data = parse_histfactory_xml(toplvlxml)
  with open(output,'w') as f:
    f.write(yaml.safe_dump(parsed_data,default_flow_style = False))


@toplevel.command()
@click.argument('rootfile')
@click.argument('workspace')
@click.argument('channel')
@click.argument('observable')
@click.argument('components')
@click.argument('parpointfile')
@click.option('-o','--output',default = 'plot.pdf')
def plot_channel(rootfile,workspace,channel,observable,components,parpointfile,output):
  f = ROOT.TFile.Open(rootfile)
  ws = f.Get(workspace)

  parpoint_data = yaml.load(open(parpointfile))
  for name,val in parpoint_data.iteritems():
    ws.var(name).setVal(val)

  plot(ws,channel,observable,components.split(','),output)
  
if __name__=='__main__':
  toplevel()