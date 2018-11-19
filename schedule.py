# Dependencies:
from pymprog import *  # pip install pymprog
from icalendar import * # pip install icalendar
from datetime import * 
from swiglpk import *  # pip install swiglpk
import pytz # pip install pytz
from tzlocal import get_localzone

################################################################################
# Helper functions
################################################################################

def split(e):
  """ 
  Splits long events (> 2 hours) in two new separate events (with different
  UID).  This is intended for Friday's 4 hours lab slots. 
  """
  twoHours = timedelta(seconds = 60 * 60 * 2)
  start = e['DTSTART'].dt
  end = e['DTEND'].dt
  if (end - start <= twoHours):
    return [e]
  mid = vDDDTypes(start + twoHours)
  e1 = e.copy()
  e2 = e.copy()
  e1['DTEND'] = mid
  e2['DTSTART'] = mid
  e2['UID'] = e2['UID'] + 'b'
  return [e1, e2]

def partition(cal):
    """
    Parition the events in the calendar in 3 dictionaries (indexed by start
    date) using the description field (grading, labs, exercises).
    """ 
    (grads, labs, exs) = ([], [], [])
    for e in cal.walk('VEvent'):
        desc = e['DESCRIPTION']
        if "Laboration\nPresentation" in desc:
          grads.append(e)
        elif "Laboration" in desc:
          labs += split(e)
        elif "Exercise" in desc:
          exs.append(e)
    return [ { e['DTSTART'].dt : e for e in d } for d in (grads, labs, exs) ] 

def mkAttendee(name):
  """ Create an address object for a grader """
  a = vCalAddress(name) # "MAILTO:" + mail[i] for mail invite
  a.params['cn'] = name 
  return a

################################################################################
# Report
#################################################################################

def summary(d, events):
  """ Per grader view of the events contained in the dictionary d """
  kd = sorted(d.keys())
  ts = [ (i,j) for (i,j) in kd if d[i,j].primal ]
  r = { k : [] for k in zip(*kd)[0] }
  for (i,j) in ts:
    e = events[j]
    r[i].append(e)
  return r

def fmt_budget(k, u, a):
  fmt = "    {}: {} / {}"
  return fmt.format(k, u, a)

def fmt_budget_summary(d):
  title = "Hour count:\n"
  body = [fmt_budget(k, b[0], b[1]) for (k, b) in sorted(d.items())]
  return "\n".join([title] + body)

def fmt_slot(e) :
  start = e['DTSTART'].dt.astimezone(get_localzone())
  end = e['DTEND'].dt.astimezone(get_localzone())
  loc = e['LOCATION']
  s1 = start.strftime("%a %d %b %H:%M")
  s2 = end.strftime("%H:%M")
  s3 = " @ " + loc if loc else ""
  return "    " + s1 + " - " + s2 + s3
 
def fmt_summary(desc, es):
  title = desc + ":\n" 
  body = [fmt_slot(e) for e in es]
  return "\n".join([title] + body)

def sep(): return "\n\n" + 80 * "-" + "\n\n"

def report(T, budget, *ss): 
  with open("report.md", "wt") as r:
    title = "Report - IFP 18\n"
    pre = fmt_budget_summary(budget)
    r.write("\n".join([title,pre]))
    for k in T:
        r.write(sep())
        r.write("### " + k + "\n\n")
        tt = [fmt_summary(desc, s[k]) for (desc, s) in ss]
        r.write("\n\n".join(tt))
    r.write(sep())

################################################################################
# Create calendars 
################################################################################

def mkCals(A, events):
  """ Create a complete calendar with all grader and one for each grader """
  def mkCal(pid):
    return Calendar(PRODID  = pid , VERSION = 2.0) # version 2.0 is important!

  full_cal = mkCal(Course) 
  single_cal = { k : mkCal(Course + k) for k in A.keys() }
 
  for e in events.values():
    full_cal.add_component(e)
    for k in e['ATTENDEE']:
      e1 = e.copy()
      e1['UID'] = k + e1['UID']
      single_cal[k].add_component(e1)

  return (full_cal, single_cal)

################################################################################

###########
# Parsing #
###########

# Name of the timeEdit ics file for the course.
cal_file = 'TimeEdit_TKDAT-1_N1COS-1-GU_TDA555_2018-08-31_09_03.ics'
with open(cal_file, 'rb') as g:
  cal = Calendar.from_ical(g.read())

(grads, labs, exs) = partition(cal)
events = { k : e for (k, e) in grads.items() + labs.items() + exs.items() }


#########
# Model # 
#########
Course = 'IFP 2018 - TA schedule'
M = begin(Course)

# Variables 
phd = { 'Marco'    : "vassena@chalmers.se"
      , 'Elisabet' : "elilob@chalmers.se"
      # , 'Matthi' : ""
      # , 'Sola'     : ""
      , 'Benjamin' : ""
      }
msc = { 'Henrik' : "henrost@student.chalmers.se"
      , 'Sarosh' : "sarosh.nasir@gmail.com;" 
      , 'Adi' : "hrustic@student.chalmers.se" 
      , 'Karin' : "karin.wibergh@gmail.com" 
      }

mail = { k : v for (k,v) in phd.items() + msc.items()}
T = sorted(phd.keys() + msc.keys())
B = var('budget', T)

# Domains
Es = sorted(exs.keys())
Gs = sorted(grads.keys())
Ls = sorted(labs.keys())
slots = sorted(Es + Gs + Ls)

Y = 2018
Sep = 9
Oct = 10

# When you won't be able to make it?
Clash = { 'Marco'    : { date(Y,Sep,d) for d in {6, 11} } 
                     | { date(Y,Oct,d) for d in {22, 23, 24} }
        , 'Elisabet' : { date(Y,Oct,d) for d in xrange(8, 16 + 1) }
                     | { date(Y,Sep,d) for d in {14, 17, 19, 20} } # Octopi Seminar
        , 'Henrik'   : { date(Y,Oct,1) }
        # , 'Matthi'   : { date(Y,Sep,d) for d in xrange(22, 29 + 1) }
        # , 'Sola'     : { date(Y,Sep,d) for d in xrange(12, 20 + 1) } 
        , 'Karin'    : { date(Y,Sep,d) for d in xrange(3, 9 + 1) } 
        , 'Adi'      : { date(Y,Sep,d) for d in {7, 14} }
                     | { date(Y,Sep,d) for d in {20} } 
                     | { date(Y,Oct,d) for d in {4, 11, 18, 25} }
        , 'Benjamin' : { date(Y,Sep,d) for d in xrange(1, 9) }
        , 'Sarosh'   : { date(Y,Sep,d) for d in {10, 17, 24} } # no mondays (Sep)
                     | { date(Y,Oct,d) for d in {1, 8, 15, 22} } # no mondays (Oct)
                     | { date(Y,Sep,d) for d in {5, 12, 19, 26} } # no wed (Sep)
                     | { date(Y,Oct,d) for d in {3, 10, 17, 24} } # no wed (Oct)
        }

# 1 if T has to serve on a time slot
E = var('exercise', iprod(T, Es), bool)
G = var('grading', iprod(T, Gs), bool)
L = var('labs', iprod(T, Ls), bool)

# Penalty: it's used to relax constraints
PE = var('penalty exercise', iprod(T, Es), int)
PG = var('penalty grading', iprod(T, Gs), int)

# D[i,j] is the absolute value of the difference in the number of hours between
# TA i and j.
D = var('delta', iprod(T,T))

###############
# Constraints #
###############

# TODO: create an object for TA to store all this information
# Budget
for i in {'Marco', 'Elisabet'} :
    B[i] <= 130

for i in msc.keys() + ['Benjamin'] :
    B[i] <= 90

# Count hours
for i in B.keys():
    B[i] == sum ([2 * L[i,j] for j in Ls] +
                 [2 * G[i,h] for h in Gs] +
                 [3 * E[i,k] for k in Es])

# 4 TA per lab
for j in Ls:
    sum( L[i,j] for i in T ) == 4

# 3 TA per exercise session
for j in Es:
    sum( E[i,j] for i in T ) == 3

# same msc TA for exercises
for k in msc:
    for i in Es:
        for j in Es:
            E[k,i] == E[k,j] # + PE[k,j]

# Always one PhD at exercise
for j in Es:
    sum(E[i,j] for i in phd.keys()) == 1

# All TAs at grading
for j in Gs:
  n = 7 if j.date().weekday() == 0 else 5 # 7 on Monday, 5 otherwise (tuesday)
  sum( G[i,j] + PG[i,j] for i in T ) >= n # TODO: It should be ==

# Either exercise on Monday or grading on Tuesday
# Too strict with few TAs
#for i in msc.keys():
#  for j in Es:
#    tuesdays = {k for k in Gs if k.date().weekday() == 1}
#    for k in tuesdays:
#        E[i,j] + G[i,k] <= 1

# Clashes
for d in [L,E,G]:
  for (j,k) in d.keys(): 
      #print "".join(["Clash?", str(k.date()), str(j), str(k.date() in Clash.get(j,{}))])
      if k.date() in Clash.get(j,{}):
        d[j,k] == 0

# Compute delta
for i in T:
  for j in T:
     D[i,j] <= 10  # Only small bias
     # compute delta (absolute value)
     B[i] - B[j] <= D[i,j]
     B[j] - B[i] <= D[i,j]

# Objective function
# Minimize penalties and biased schedules
minimize(sum ( [ 10000 * PG[i,j] for i in T for j in Gs ] 
             + [ 25 * PE[i,j]   for i in T for j in Es ]   
             + [ D[i,j]         for i in T for j in T  ] ))

####################
# Solve and report #
####################

verbose(True)
solver( 'intopt'
      , mip_gap = 3.0, # Or we look for ever without really improving
    )
solve()
stat = M.get_status() 

if stat == GLP_INFEAS or stat == GLP_NOFEAS:
  print(KKT())
  exit("No solution: relax constraints")
elif stat == GLP_SOL or stat == GLP_FEAS or stat == GLP_OPT:
  budget_sum= { k : (B[k].primal , B[k].bounds[1]) for k in sorted(B.keys()) }
  ex_sum = summary(E, events)
  gr_sum = summary(G, events)
  lab_sum = summary(L, events)

  # Text report
  ss = [ ("Exercises", ex_sum)
       , ("Labs", lab_sum)
       , ("Grading", gr_sum)]
  report(T, budget_sum, *ss)  
   
  # Ics Report (calendar)

  # Attende object for each TA
  A = { k : mkAttendee(k) for k in T }
  all_sum = ex_sum.items() + gr_sum.items() + lab_sum.items()

  # Add TA to ics events
  for (i, es) in all_sum:
    for e in es:
      e.add('ATTENDEE', A[i])

  (full_cal, single_cal) = mkCals(A, events)
  
  # Write calendars
  with open("full.ics","wb") as out:
    out.write(full_cal.to_ical())

  for (k, cal) in single_cal.items():
    with open(k + ".ics", "wb") as out:
      out.write(cal.to_ical())

#sensitivity() # sensitivity report (bug!)
end()
