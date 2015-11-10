
# coding: utf-8

# In[65]:

# make the code as Python 3 compatible as possible
from __future__ import print_function, division

import pypsa

from pypsa.dicthelpers import attrfilter

import datetime
import pandas as pd

import networkx as nx

import numpy as np

from itertools import chain


# In[66]:

#Build the Network object, which stores all other objects

network = pypsa.Network()

#Build the snapshots we consider for the first T hours in 2015

T = 10

network.snapshots = pd.to_datetime([datetime.datetime(2015,1,1) + datetime.timedelta(hours=i) for i in range(T)])

network.now = network.snapshots[0]

print("network:",network)
print("snapshots:",network.snapshots)
print("current snapshot:",network.now)


# In[67]:

#add fuel types
network.add("Source","gas",co2_emissions=0.24)
network.add("Source","wind")

network.co2_limit = 1000


# In[68]:

#The network is two three-node AC networks connected by 2 point-to-point DC links

#building block
n = 3

#copies
c = 2


#add buses
for i in range(n*c):
    network.add("Bus",i,v_nom="380")

#add lines
for i in range(n*c):
    network.add("Line",i,
                bus0=network.buses[str(i)],
                bus1=network.buses[str(n*(i // n)+ (i+1) % n)],
                x=np.random.random(),
                s_nom=0,
                capital_cost=0.1,
                s_nom_min=0,
                s_nom_extendable=True)

#add HVDC lines
for i in range(2):
    network.add("TransportLink","TL %d" % (i),
                bus0=network.buses[str(i)],
                bus1=network.buses[str(3+i)],
                p_nom=1000,
                p_max=900,
                p_min=-900,
                s_nom=0,
                capital_cost=0.1,
                s_nom_min=0,
                s_nom_extendable=True)


#add loads
for i in range(n*c):
    network.add("Load",i,bus=network.buses[str(i)])

#add some generators
for i in range(n*c):
    #storage
    network.add("StorageUnit","Storage %d" % (i),
                bus=network.buses[str(i)],
                p_nom=0,source="storage",
                marginal_cost=2,
                capital_cost=1000,
                p_nom_extendable=True,
                p_max_pu_fixed=1,
                p_min_pu_fixed=-1,
                efficiency_store=0.9,
                efficiency_dispatch=0.95,
                standing_loss=0.01,
                max_hours=6)
    #wind generator
    network.add("Generator","Wind %d" % (i),bus=network.buses[str(i)],
                p_nom=100,source=network.sources["wind"],dispatch="variable",
                marginal_cost=0,
                capital_cost=1000,
                p_nom_extendable=True,
                p_nom_max=None,
                p_nom_min=100)
    #gas generator
    network.add("Generator","Gas %d" % (i),bus=network.buses[str(i)],
                p_nom=0,source=network.sources["gas"],dispatch="flexible",
                marginal_cost=2,
                capital_cost=100,
                efficiency=0.35,
                p_nom_extendable=True,
                p_nom_max=None,
                p_nom_min=0)


# In[69]:

#now attach some time series

network.load_series = pd.DataFrame(index = network.snapshots,
                                       columns = [load_name for load_name in network.loads],
                                       data = 1000*np.random.rand(len(network.snapshots), len(network.loads)))

for load in network.loads.itervalues():
    load.p_set = network.load_series[load.name]



wind_generators = attrfilter(network.generators,source=network.sources["wind"])

network.wind_series = pd.DataFrame(index = network.snapshots,
                                       columns = [gen.name for gen in wind_generators],
                                       data = np.random.rand(len(network.snapshots), len(wind_generators)))


for generator in wind_generators:
    generator.p_set = network.wind_series[generator.name]*generator.p_nom
    generator.p_max_pu = network.wind_series[generator.name]

for su in network.storage_units.itervalues():
    su.state_of_charge[network.snapshots[0]] = 0.0


for transport_link in network.transport_links.itervalues():
    transport_link.p_set = pd.Series(index = network.snapshots, data=(200*np.random.rand(len(network.snapshots))-100))


# In[70]:

print(network.wind_series)


# In[71]:

network.build_graph()


# In[72]:

network.determine_network_topology()


# In[73]:

print(network.sub_networks)


# In[74]:

snapshots = network.snapshots[:4]
network.lopf(snapshots=snapshots)


# In[75]:

print("Generator and storage capacities:\n")

for one_port in chain(network.generators.itervalues(),network.storage_units.itervalues()):
    print(one_port,one_port.p_nom)

print("\n\nBranch capacities:\n")

for branch in network.branches.itervalues():
    print(branch,branch.s_nom)

for snapshot in snapshots:

    print("\n"*2+"For time",snapshot,":\nBus injections:")

    for bus in network.buses.itervalues():
        print(bus,bus.p[snapshot])
    print("Total:",sum([bus.p[snapshot] for bus in network.buses.itervalues()]))


# In[76]:

for branch in network.branches.itervalues():
    print(branch,branch.p1[network.now])


# In[77]:

network.now = network.snapshots[0]

print("Comparing bus injection to branch outgoing for %s:",network.now)

for sub_network in network.sub_networks.itervalues():

    print("\n\nConsidering sub network",sub_network,":")

    for bus in sub_network.buses.itervalues():

        print("\n%s" % bus)

        print("power injection (generators - loads + Transport feed-in):",bus.p[network.now])

        print("generators - loads:",sum([g.sign*g.p[network.now] for g in bus.generators.itervalues()])                        + sum([l.sign*l.p[network.now] for l in bus.loads.itervalues()]))

        total = 0.0

        for branch in sub_network.branches.itervalues():
            if bus == branch.bus0:
                print("from branch:",branch,branch.p0[network.now])
                total +=branch.p0[network.now]
            elif bus == branch.bus1:
                print("to branch:",branch,branch.p1[network.now])
                total +=branch.p1[network.now]
        print("branch injection:",total)


# In[78]:

for su in network.storage_units.values():
    print(su,su.p_nom,"\n",su.state_of_charge,"\n",su.p)


# In[79]:

for gen in network.generators.itervalues():
    print(gen,gen.source.co2_emissions*(1/gen.efficiency))


# In[80]:

network.co2_limit