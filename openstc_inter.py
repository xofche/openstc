# -*- coding: utf-8 -*-

##############################################################################
#
#    OpenCivil module for OpenERP, module Etat-Civil
#    Copyright (C) 200X Company (<http://website>) pyf
#
#    This file is a part of penCivil
#
#    penCivil is free software: you can redistribute it and/or modify
#    it under the terms of the GNU General Public License as published by
#    the Free Software Foundation, either version 3 of the License, ors_user
#    (at your option) any later version.
#
#    penCivil is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU General Public License for more details.
#
#    You should have received a copy of the GNU General Public License
#    along with this program.  If not, see <http://www.gnu.org/licenses/>.
#
#############################################################################
#import logging

import types

import re
import time
import operator
import logging
import netsvc
import pytz
from osv.orm import browse_record, browse_null
from osv import fields, osv, orm
from datetime import datetime, timedelta
from dateutil import *
from dateutil.tz import *
from tools.translate import _

#_logger = logging.getLogger(__name__)

def _get_request_states(self, cursor, user_id, context=None):
    return (
                ('wait', 'Wait'),('confirm', 'To be confirm'),('valid', 'Valid'),('refused', 'Refused'),('closed', 'Closed')
            )

def _get_param(params, key):
    if params.has_key(key) == True :
        if params[key]!=None or params[key]!='' or params[key]>0 :
            return params[key]
    return False;


def _test_params(params, keys):
    param_ok = True
    for key in keys :
        if params.has_key(key) == False :
            param_ok = False
        else :
            if params[key]==None or params[key]=='' or params[key]==0 :
                param_ok = False
    return param_ok


def send_email(self, cr, uid, ids, params, context=None):

    ask_obj = self.pool.get('openstc.ask')
    ask = ask_obj.browse(cr, uid, ids[0], context)

    user_obj = self.pool.get('res.users')
    user = user_obj.read(cr, uid, uid,
                                    ['company_id'],
                                    context)

    company_obj = self.pool.get('res.company')
    company = company_obj.read(cr, uid, user['company_id'][0],
                            ['email'],
                            context)

    email_obj = self.pool.get("email.template")
    ir_model = self.pool.get("ir.model").search(cr, uid, [('model','=',self._name)])

    email_tmpl_id = email_obj.create(cr, uid, {
                #'name':'modèle de mail pour résa annulée',
                'name':'Suivi de la demande ' + ask.name,
                'model_id':ir_model[0],
                'subject':'Suivi de la demande ' + ask.name,
                'email_from': company['email'],
                'email_to': ask.partner_email or ask.people_email or False,
                'body_text':"Votre Demande est à l'état " + params['email_text'] +  "\r" +
                    "pour plus d'informations, veuillez contacter la mairie de Pont L'abbé au : 0240xxxxxx"
        })

    mail_id = email_obj.send_mail(cr, uid, email_tmpl_id, ids[0])
    #to uncomment
    #self.pool.get("mail.message").send(cr, uid, [mail_id])

    return True


class service(osv.osv):
    _inherit = "openstc.service"

    _columns = {
        'asksBelongsto': fields.one2many('openstc.ask', 'service_id', "asks"),
        'category_ids':fields.many2many('openstc.task.category', 'openstc_task_category_services_rel', 'service_id', 'task_category_id', 'Categories'),
    }
service()


class site(osv.osv):
    _inherit = "openstc.site"
    _columns = {
        'asksBelongsto': fields.one2many('openstc.ask', 'site1', "asks"),
        'intervention_ids': fields.one2many('project.project', 'site1', "Interventions", String="Interventions"),
        }

class users(osv.osv):
    _inherit = "res.users"
    _columns = {
            'tasks': fields.one2many('project.task', 'user_id', "Tasks"),
            'contact_id': fields.one2many('res.partner.address', 'user_id', "Partner"),

    }

class team(osv.osv):
    _inherit = "openstc.team"
    _columns = {
        'tasks': fields.one2many('project.task', 'team_id', "Tasks"),

        }

class res_partner(osv.osv):
    _name = "res.partner"
    _description = "res.partner"
    _inherit = "res.partner"
    _rec_name = "name"



    _columns = {
         'service_id':fields.many2one('openstc.service', 'Service du demandeur'),
         'technical_service_id':fields.many2one('openstc.service', 'Service technique concerné'),
         'technical_site_id': fields.many2one('openstc.site', 'Default Site'),

    }
res_partner()


class res_partner_address(osv.osv):
    _description ='Partner Addresses st'
    _name = 'res.partner.address'
    _inherit = "res.partner.address"
    _order = 'type, name'


    _columns = {
        'user_id': fields.many2one('res.users', 'User'),
    }

    def create(self, cr, uid, data, context=None):
        res = super(res_partner_address, self).create(cr, uid, data, context)
        self.create_account(cr, uid, [res], data, context)

        return res



    def write(self, cr, uid, ids, data, context=None):

        user_obj = self.pool.get('res.users')
        partner_address = self.read(cr, uid, ids[0],
                                    ['user_id'],
                                    context)

        if partner_address.has_key('user_id')!= False :
            if partner_address['user_id'] != False :
                user = user_obj.browse(cr, uid, partner_address['user_id'][0], context=context)
                if user.id != 0 and  _test_params(data, ['login','password','name','email'])!= False :
                    user_obj.write(cr, uid, [user.id], {
                                    'name': data['name'],
                                    'firstname': data['name'],
                                    'user_email': data['email'],
                                    'login': data['login'],
                                    'new_password': data['password'],
                            }, context=context)

            else :
                self.create_account(cr, uid, ids, data, context)



        res = super(res_partner_address, self).write(cr, uid, ids, data, context)
        return res

    def create_account(self, cr, uid, ids, params, context):
        if _test_params(params, ['login','password','name','email'])!= False :

            company_ids = self.pool.get('res.company').name_search(cr, uid, name='STC')
            if len(company_ids) == 1:
                params['company_id'] = company_ids[0][0]
            else :
                params['company_id'] = 1;

            user_obj = self.pool.get('res.users')

            group_obj = self.pool.get('res.groups')
            #Get partner group (code group=PART)
            group_id = group_obj.search(cr, uid, [('code','=','PART')])[0]
            user_id = user_obj.create(cr, uid,{
                    'name': params['name'],
                    'firstname': params['name'],
                    'user_email': params['email'],
                    'login': params['login'],
                    'new_password': params['password'],
                    'groups_id' : [(6, 0, [group_id])],
                    })
            self.write(cr, uid, ids, {
                    'user_id': user_id,
                }, context=context)


res_partner_address()

#----------------------------------------------------------
# Employees
#----------------------------------------------------------


#----------------------------------------------------------
# Tâches
#----------------------------------------------------------

class task(osv.osv):
    _name = "project.task"
    _description = "Task ctm"
    _inherit = "project.task"
    __logger = logging.getLogger(_name)



    #Overrides _is_template method of project module
    def _is_template(self, cr, uid, ids, field_name, arg, context=None):
        res = {}
        for task in self.browse(cr, uid, ids, context=context):
            res[task.id] = True
        return res




    #Calculates if agent belongs to 'arg' code group
    def _get_active(self, cr, uid, ids, fields, arg, context):
         res = {}
         user_obj = self.pool.get('res.users')
         task_obj = self.pool.get('project.task')
         team_obj = self.pool.get('openstc.team')
         project_obj = self.pool.get('project.project')

         user = user_obj.browse(cr, uid, uid,context)


         for id in ids:
            task = task_obj.browse(cr, uid, id, context=context)

            task_user_id = task_team_id = team_manager_id = task_project_id = project_service_id = False
            if isinstance(task.user_id, browse_null)!= True :
                task_user_id = task.user_id.id

            if isinstance(task.team_id, browse_null)!= True :
                task_team_id = task.team_id.id
                team = team_obj.browse(cr, uid, task.team_id.id, context=context)

            if task_team_id!= False :
                if isinstance(team.manager_id, browse_null)!= True :
                    team_manager_id = team.manager_id.id

            if isinstance(task.project_id, browse_null)!= True :
                task_project_id = task.project_id.id

            if task_project_id != False :
                project = project_obj.browse(cr, uid, task_project_id, context=context)
                try:
                   if isinstance(project.service_id, browse_null)!= True :
                       project_service_id = project.service_id.id
                except orm.except_orm, inst:
                     project_service_id = False

            belongsToOfficer = (task_user_id!=False and task_user_id == user.id) or (team_manager_id!=False and team_manager_id == task_user_id)
            belongsToTeam = task_team_id in ( t.id for t in user.team_ids )
            belongsToServiceManager = project_service_id in (s.id for s in user.service_ids) and user.isManager == True
            res[id] = True if belongsToOfficer or belongsToTeam or belongsToServiceManager or user.isDST else False
         return res
    
    def getUserTasksList(self, cr, uid, domain=[], fields=[], context=None):
        #in taskLists, absences are removed from result
        domain.extend([('state','!=','absent')])
        #first i get tasks with filter asked by UI
        res_ids = self.search(cr, uid, domain, context=context)
        res_filtered = [item[0] for item in self._get_active(cr, uid, res_ids, 'active', False, context=context).items() if item[1]]
        ret = self.read(cr, uid, res_filtered, fields, context=context)
        return ret
    
    #if tasks has an inter, returns service of this inter, else returns user services (returns empty list in unexpected cases)
    def get_services_authorized(self, cr, uid, id, context=None):
        ret = []
        if id:
            task = self.browse(cr, uid, id,context=context)
            if task.project_id:
                ret = [task.project_id.service_id and task.project_id.service_id.id] or []
            else:
                ret = self.pool.get("res.users").read(cr, uid, uid, ['service_ids'])['service_ids']
        else:
            ret = self.pool.get("res.users").read(cr, uid, uid, ['service_ids'])['service_ids']
        return ret
    
    def get_vehicules_authorized(self, cr, uid, id, context=None):
        service_id = self.get_services_authorized(cr, uid, id, context=context)
        ret = []
        if service_id:
            vehicule_ids = self.pool.get("openstc.equipment").search(cr, uid, ['&','|',('technical_vehicle','=',True),('commercial_vehicle','=',True),('service_ids','in',service_id)])
            ret = self.pool.get("openstc.equipment").read(cr, uid, vehicule_ids, ['id','name','type'],context=context)
        return ret
    
    def get_materials_authorized(self, cr, uid, id, context=None):
        service_id = self.get_services_authorized(cr, uid, id, context=context)
        ret = []
        if service_id:
            material_ids = self.pool.get("openstc.equipment").search(cr, uid, ['&','|',('small_material','=',True),('fat_material','=',True),('service_ids','in',service_id)])
            ret = self.pool.get("openstc.equipment").read(cr, uid, material_ids, ['id','name','type'],context=context)
        return ret
        
    #user can make survey of the task if it's an officer task, or a team task and user is a foreman / manager
    def _task_survey_rights(self, cr, uid, record, groups_code):
        ret = False
        if not record.team_id:
            ret = True
        else:
            ret = 'OFFI' not in groups_code
        return ret

    _actions = {
        'print':lambda self,cr,uid,record, groups_code: record.state in ('draft','open'),
        'cancel':lambda self,cr,uid,record, groups_code: record.state == 'draft',
        'delete':lambda self,cr,uid,record, groups_code: record.state == 'draft',
        'replan': lambda self,cr,uid,record, groups_code: record.state == 'done',
        'normal_mode_finished': lambda self,cr,uid,record, groups_code: self._task_survey_rights(cr, uid, record, groups_code) and record.state == 'open',
        'normal_mode_unfinished': lambda self,cr,uid,record, groups_code: self._task_survey_rights(cr, uid, record, groups_code) and record.state == 'open',
        'light_mode_finished': lambda self,cr,uid,record, groups_code: self._task_survey_rights(cr, uid, record, groups_code) and record.state == 'draft',
        'light_mode_unfinished': lambda self,cr,uid,record, groups_code: self._task_survey_rights(cr, uid, record, groups_code) and record.state == 'draft',
        'modify': lambda self,cr,uid,record, groups_code: True,

        }

    def _get_actions(self, cr, uid, ids, myFields ,arg, context=None):
        #default value: empty string for each id
        ret = {}.fromkeys(ids,'')
        groups_code = []
        groups_code = [group.code for group in self.pool.get("res.users").browse(cr, uid, uid, context=context).groups_id if group.code]

        #evaluation of each _actions item, if test returns True, adds key to actions possible for this record
        for record in self.browse(cr, uid, ids, context=context):
            #ret.update({inter['id']:','.join([key for key,func in self._actions.items() if func(self,cr,uid,inter)])})
            ret.update({record.id:[key for key,func in self._actions.items() if func(self,cr,uid,record,groups_code)]})
        return ret

#    def test_check_permission(self, cr, uid, ids, action, context=None):
#        ret = False
#        for task in self.browse(cr, uid, ids, context=context):
#            if action in task.actions:
#                ret = True
#            else:
#                print 'Error, user does not have %s right access'% action

        return ret
    
    def _get_task_from_inter(self, cr, uid, ids, context=None):
        return self.search(cr, uid, [('project_id','in',ids)],context=context)
    
    _columns = {
        'active':fields.function(_get_active, method=True,type='boolean', store=False),
        'ask_id': fields.many2one('openstc.ask', 'Demande', ondelete='set null', select="1"),
        'project_id': fields.many2one('project.project', 'Intervention', ondelete='set null'),
        'equipment_ids':fields.many2many('openstc.equipment', 'openstc_equipment_task_rel', 'task_id', 'equipment_id', 'Equipments'),
        'parent_id': fields.many2one('project.task', 'Parent Task'),
        'intervention_assignement_id':fields.many2one('openstc.intervention.assignement', 'Assignement'),
        'absent_type_id':fields.many2one('openstc.absent.type', 'Type d''abscence'),
        'category_id':fields.many2one('openstc.task.category', 'Category'),
        'state': fields.selection([('absent', 'Absent'),('draft', 'New'),('open', 'In Progress'),('pending', 'Pending'), ('done', 'Done'), ('cancelled', 'Cancelled')], 'State', readonly=True, required=True,
                                  help='If the task is created the state is \'Draft\'.\n If the task is started, the state becomes \'In Progress\'.\n If review is needed the task is in \'Pending\' state.\
                                  \n If the task is over, the states is set to \'Done\'.'),
        'team_id': fields.many2one('openstc.team', 'Team'),

        'km': fields.integer('Km', select=1),
        'oil_qtity': fields.float('oil quantity', select=1),
        'oil_price': fields.float('oil price', select=1),
        'site1':fields.related('project_id','site1',type='many2one',relation='openstc.site', string='Site',store={'project.task':[lambda self,cr,uid,ids,ctx={}:ids, ['project_id'], 10],
                                                                                                                  'project.project':[lambda self,cr,uid,ids,ctx={}:_get_task_from_inter, ['site1'],11]}),
        'cancel_reason': fields.text('Cancel reason'),
        'actions':fields.function(_get_actions, method=True, string="Actions possibles",type="char", store=False),

    }

    _defaults = {'active': lambda *a: True, 'user_id':None}


    def createOrphan(self, cr, uid, ids, params, context=None):

        task_obj = self.pool.get(self._name)

        self.updateEquipment(cr, uid, params, context)

        res = super(task, self).create(cr, uid, params, context)
        new_task = task_obj.browse(cr, uid, res, context)

        self.createWork(cr, uid, new_task, params, context)

        return res


    def reportHours(self, cr, uid, ids, params, context=None):

        #report_hours
        #remaining_hours

        task_obj = self.pool.get(self._name)
        #Get current task
        task = task_obj.browse(cr, uid, ids[0], context)
        #do nothing if task no found or not report hours
        if task==None or task == False : return False
        if not _get_param(params, 'report_hours') : return False

        project_obj = self.pool.get('project.project')
        ask_obj = self.pool.get('openstc.ask')
        #Get intervention's task
        if task.project_id!=None and task.project_id!=False :
            if task.project_id.id > 0 :
                project = project_obj.browse(cr, uid, [task.project_id.id], context=context)[0]
                #update intervention state
                if (project.state != 'template'):
                    #update intervention state  : pending because remaining_hours>0
                    project_obj.write(cr, uid, project.id, {
                        'state': 'pending',
                    }, context=context)

        #Prepare equipment list
        if params.has_key('equipment_ids') and len(params['equipment_ids'])>0 :
            equipments_ids = params['equipment_ids']
        else :
            equipments_ids = []
        #update mobile equipment kilometers
        self.updateEquipment(cr, uid, params, context)

        #Records report time
        self.createWork(cr, uid, task, params, context)

        self.__logger.warning('----------------- Write task %s ------------------------------', ids[0])
        #Update Task
        task_obj.write(cr, uid, ids[0], {
                'state': 'done',
                'date_start': task.date_start or _get_param(params, 'date_start'),
                'date_end': task.date_end or _get_param(params, 'date_end'),
                'team_id': task.team_id.id or _get_param(params, 'team_id'),
                'user_id': task.user_id.id or _get_param(params, 'user_id'),
                'equipment_ids': [[6, 0, equipments_ids]],
                'remaining_hours': 0,
                'km': 0 if params.has_key('km')== False else params['km'],
                'oil_qtity': 0 if params.has_key('oil_qtity')== False else params['oil_qtity'],
                'oil_price': 0 if params.has_key('oil_price')== False else params['oil_price'],
            }, context=context)



        ask_id = 0
        if project!=None :
            ask_id = project.ask_id.id



        if _test_params(params,['remaining_hours'])!=False:
           #Not finnished task : Create new task for planification
           task_obj.create(cr, uid, {
                 'name'              : task.name,
                 'parent_id'         : task.id,
                 'project_id'        : task.project_id.id or False,
                 'state'             : 'draft',
                 'planned_hours'     : 0 if params.has_key('remaining_hours')== False else params['remaining_hours'],
                 'remaining_hours'   : 0 if params.has_key('remaining_hours')== False else params['remaining_hours'],
                 'user_id'           : None,
                 'team_id'           : None,
                 'date_end'          : None,
                 'date_start'        : None,
             }, context)
        else:
            #Finnished task
            all_task_finnished = True

            #if task is the last at ['open','pending', 'draft'] state on intervention : close intervention and ask.
            for t in project.tasks :
                if task.id!=t.id and t.state in ['open','pending', 'draft']:
                    all_task_finnished = False
                    break

            if all_task_finnished == True:
                project_obj.write(cr, uid, project.id, {
                    'state': 'closed',
                }, context=context)

                if ask_id>0 :
                    ask_obj.write(cr, uid, ask_id, {
                        'state': 'closed',
                    }, context=context)

                #TODO
                #send email ==>  email_text: demande 'closed',

        return True


    def updateEquipment(self, cr, uid, params, context):
        equipment_obj = self.pool.get('openstc.equipment')
        #Update kilometers on vehucule
        if _test_params(params,['vehicule','km'])!= False :
            equipment_obj.write(cr, uid, params['vehicule'], {
                     'km': 0 if params.has_key('km')== False else params['km']
                 }, context=context)

    def createWork(self, cr, uid, task, params, context):
        task_work_obj = self.pool.get('project.task.work')
        #update task work

        task_work_obj.create(cr, uid, {
             'name': task.name,
             #TODO : manque l'heure
             'date':  datetime.now().strftime('%Y-%m-%d') if params.has_key('date')== False  else params['date'],
             'task_id': task.id,
             'hours':  _get_param(params, 'report_hours'),
             'user_id': task.user_id.id or False,
             'team_id': task.team_id.id or False,
             'company_id': task.company_id.id or False,
            }, context=context)

    def create(self, cr, uid, vals, context=None):
        res = super(task, self).create(cr, uid, vals, context=context)
        #if task is created with reports_hours, update task_work and task values
        self.reportHours(cr, uid, [res], vals, context=context)
        return res
    
    def write(self, cr, uid, ids, vals, context=None):
        res = super(task, self).write(cr, uid, ids, vals, context=context)
        #if task(s) have hours to report, we update task works and those tasks 
        if not isinstance(ids, list):
            ids = [ids]
        self.reportHours(cr, uid, ids, vals, context=context)
        return res

    def cancel(self, cr, uid, ids, params, context={}):
        """
        Cancel Task
        """

        if not isinstance(ids,list): ids = [ids]
        for task in self.browse(cr, uid, ids, context=context):
            vals = {}

            vals.update({'state': 'cancelled'})
            vals.update({'cancel_reason': _get_param(params, 'cancel_reason') })
            vals.update({'remaining_hours': 0.0})
            if not task.date_end:
                vals.update({ 'date_end':time.strftime('%Y-%m-%d %H:%M:%S')})
            self.write(cr, uid, [task.id],vals, context=context)
            message = _("The task '%s' is done") % (task.name,)
            self.log(cr, uid, task.id, message)
        return True

    def planTasks(self, cr, uid, ids, params, context=None):

        """
        Plan tasks after drag&drop task on planning

        :param cr: database cursor
        :param uid: current user id
        :param ids: list of ids
        :param params: contains
            startWorkingTime : date/heure début de journée travaillée
            endWorkingTime : date/heure fin de journée
            startLunchTime : date/heure début pause déjeuner
            endLunchTime : date/heure fin pause déjeuner
            startDt: date/heure du début de la plage souhaitée
            teamMode : boolean, calendrier d'une équipe ou d'un agent
            calendarId : celui de l'agent / ou celui de l'équipe, selon le teamMode

        This method is used when plan tasks from client

        """

        self.log(cr, uid, ids[0], "planTasks")
        if not len(ids) == 1: raise Exception('Pas de tâche à planifier')

        #ret
        results = {}
        #date format
        timeDtFrmt = "%Y-%m-%d %H:%M:%S"

        #Get current task
        currentTask = self.browse(cr, uid, ids[0], context=context)
        #if task belongs to an intervention
        if currentTask.project_id:
            #Copy is true when intervention is a template
            copy = self.pool.get('project.project').is_template(cr, uid, [currentTask.project_id.id], context=context)


        if 'cpt' not in params:  params['cpt'] = -1
        if 'number' not in params: params['number'] = 0
        #Init time to plan
        if 'timeToPlan' not in params: params['timeToPlan'] = currentTask.planned_hours
        #Planning is complete : return current task upgraded
        elif params['timeToPlan']==0 or not params['startDt']:
            return  params['results']

        teamMode = params['teamMode']
        calendarId = params['calendarId']

        #Get all events on 'startDt' for officer or team 'calendarId'
        if 'events' not in params :
#            try:
            events = self.getTodayEventsById(cr, uid, ids, params, timeDtFrmt, context)
#            except Exception, e:
#                return e
        else:
            events = params['events']

        cpt = params['cpt']
        startDt = params['startDt']
        size = len(events)

        while True:
           cpt+=1
           #Get end date
           endDt = startDt + timedelta(hours=params['timeToPlan'])
           if cpt<size:
               e = events[cpt]
               if(startDt >= e['date_start'] and startDt<=e['date_end']):
                    startDt = e['date_end']
               elif startDt > e['date_start']:
                    continue
               else:
                   break
           else:
               break


        if cpt  == size:
             #Task was not completely scheduled
            results.update({
                  'name':  currentTask.name,
                  'project_id': currentTask.project_id.id,
                  'parent_id': currentTask.id if copy else False,
                  'state': 'draft',
                  'planned_hours': params['timeToPlan'],
                  'remaining_hours': params['timeToPlan'],
                  'user_id': None,
                  'team_id': None,
                  'date_end': None,
                  'date_start': None,
            })
            #Return to plan with the remaining time
            self.write(cr, uid, [currentTask.id],results, context=context)
            params['timeToPlan'] = 0
            params['results'] = results
        else:
            #Get next date
            nextDt = events[cpt]['date_start']
            #hours differences to next date
            diff = (nextDt-startDt).total_seconds()/3600

            if (params['timeToPlan'] - diff) == 0 :
                #whole task is completely schedulable (all hours) before next so timeToPlan is set to 0
                params['timeToPlan'] = 0
                endDt = nextDt
            elif (params['timeToPlan'] - diff) > 0 :
                #task is not completely schedulable
                params['timeToPlan'] = params['timeToPlan'] - diff
                endDt = nextDt
            else:
                #there is less time to plan the number of hours possible before the next date, diff is re-calculate
                params['timeToPlan'] = 0
                diff = (endDt-startDt).total_seconds()/3600


            if params['number'] > 0 :
                #The task is divided : title is changed"
                title = "(Suite-" + str(params['number']) + ")" + currentTask.name
            else:
                title = currentTask.name

            results = {
                'name': title,
                'planned_hours': diff,
                'remaining_hours': diff,
                'team_id': calendarId if teamMode else None,
                'user_id': calendarId if not teamMode else None,
                'date_start': datetime.strftime(startDt,timeDtFrmt),
                'date_end': datetime.strftime(endDt,timeDtFrmt),
                'state': 'open',
                'parent_id': currentTask.id if copy else False,
                'project_id': currentTask.project_id.id,
            }

            #All time is scheduled and intervention is not a template
            if params['timeToPlan'] == 0 and not copy:
                #Update task
                self.write(cr, uid, [currentTask.id],results, context=context)
            else:
                #Create task
                self.create(cr, uid, results);

        params['results'] = results
        params['startDt'] = endDt
        params['number'] += 1
        params['cpt'] = cpt - 1
        #re-call the method with new params
        return self.planTasks(cr, uid, ids, params, context)

    def getTodayEventsById(self, cr, uid, ids, params, timeDtFrmt, context=None):
        """
        Plan tasks after drag&drop task on planning

        :param cr: database cursor
        :param uid: current user id
        :param ids: list of ids
        :param params: contains
            startWorkingTime : date/heure début de journée travaillée
            endWorkingTime : date/heure fin de journée
            startLunchTime : date/heure début pause déjeuner
            endLunchTime : date/heure fin pause déjeuner
            startDt: date/heure du début de la plage souhaitée
            teamMode : boolean, calendrier d'une équipe ou d'un agent
            calendarId : celui de l'agent / ou celui de l'équipe, selon le teamMode

        This method is used to get events on startDt (lunch including) for officer or team (calendarId)

        """
        if not set(('startWorkingTime','endWorkingTime','startLunchTime','endLunchTime','startDt','calendarId')).issubset(params) :
            raise Exception('Erreur : il manque des paramètres pour pouvoir planifier (Heure d''embauche, heure de déjeuner...) \n Veuillez contacter votre administrateur ')

        #Date format passed by javascript client : date from utc.
        #Client swif lose the timezone because of the serialisation in JSON request (JSON.stringify)
        timeDtFrmtWithTmz = "%Y-%m-%dT%H:%M:%S.000Z"
        #Get user context
        context_tz = self.pool.get('res.users').read(cr,uid,[uid], ['context_tz'])[0]['context_tz'] or 'Europe/Paris'
        tzinfo = pytz.timezone(context_tz)

        events= []

        todayDt = datetime.now(tzinfo)
        #Calculate time differencee between utc and user's timezone
        deltaTz = int((datetime.utcoffset(todayDt).total_seconds())/3600)

        #Get Start and end working time, lunch start and stop times
        startDt = datetime.strptime(params['startDt'],timeDtFrmtWithTmz)
        startWorkingTime = startDt.replace(hour= (int(params['startWorkingTime'])-deltaTz),minute=0, second=0, microsecond=0)
        startLunchTime = startDt.replace( hour = (int(params['startLunchTime'])-deltaTz),minute=0, second=0, microsecond=0 )
        endLunchTime = startDt.replace( hour = (int(params['endLunchTime'])-deltaTz),minute=0, second=0, microsecond=0 )

        #Add in list
        events.append({'title': "lunchTime", 'date_start': startLunchTime,
                       'date_end': endLunchTime})
        endWorkingTime = startDt.replace( hour = (int(params['endWorkingTime'])-deltaTz),minute=0, second=0, microsecond=0 )
        events.append({'title': "endWorkingTime", 'date_start': endWorkingTime,
                       'date_end': endWorkingTime})

        task_ids = []
        if params['teamMode'] == True:
            #Get all tasks on 'startDt' for team
            task_ids = self.search(cr,uid,
                ['&',('date_start','>=', datetime.strftime(startWorkingTime,timeDtFrmt)),
                    ('date_start','<=', datetime.strftime(endWorkingTime,timeDtFrmt)),
                    ('team_id','=',params['calendarId'])
                ])
        else:
            #Get all tasks on 'startDt' for officer
            task_ids = self.search(cr,uid,
                ['&',('date_start','>=', datetime.strftime(startWorkingTime,timeDtFrmt)),
                    ('date_start','<=', datetime.strftime(endWorkingTime,timeDtFrmt)),
                    ('user_id','=',params['calendarId'])
                ])

        tasks = self.read(cr,uid,task_ids, ['name','date_start','date_end'])
        #Add tasks in list
        for task in tasks :
            events.append({'title': task['name'], 'date_start': datetime.strptime(task['date_start'],timeDtFrmt),
                           'date_end': datetime.strptime(task['date_end'],timeDtFrmt) })

        #Sort task
        events.sort(key=operator.itemgetter('date_start'))
        params['events'] = events
        params['startDt'] = startDt
        #Return tasks
        return events

task()

class openstc_task_category(osv.osv):

    def name_get(self, cr, uid, ids, context=None):
        if not len(ids):
            return []
        reads = self.read(cr, uid, ids, ['name','parent_id'], context=context)
        res = []
        for record in reads:
            name = record['name']
            if record['parent_id']:
                name = record['parent_id'][1]+' / '+name
            res.append((record['id'], name))
        return res

    def _name_get_fnc(self, cr, uid, ids, prop, unknow_none, context=None):
        res = self.name_get(cr, uid, ids, context=context)
        return dict(res)


    _name = "openstc.task.category"
    _description = "Task Category"
    _columns = {
        'name': fields.char('Name', size=64, required=True, select=True),
        'code': fields.char('Code', size=32),
        'complete_name': fields.function(_name_get_fnc, type="char", string='Name'),
        'parent_id': fields.many2one('openstc.task.category','Parent Category', select=True, ondelete='cascade'),
        'child_id': fields.one2many('openstc.task.category', 'parent_id', string='Child Categories'),
        'sequence': fields.integer('Sequence', select=True, help="Gives the sequence order when displaying a list of product categories."),
        'parent_left': fields.integer('Left Parent', select=1),
        'parent_right': fields.integer('Right Parent', select=1),
        'service_ids':fields.many2many('openstc.service', 'openstc_task_category_services_rel', 'task_category_id', 'service_id', 'Services'),
        'unit': fields.char('Unit', size=32),
        'quantity': fields.integer('Quantity'),
        'tasksAssigned': fields.one2many('project.task', 'category_id', "tasks"),
    }

    _sql_constraints = [
        ('category_uniq', 'unique(name,parent_id)', 'Category must be unique!'),
    ]


    _parent_name = "parent_id"
    _parent_store = True
    _parent_order = 'sequence, name'
    _order = 'parent_left'

    def _check_recursion(self, cr, uid, ids, context=None):
        level = 100
        while len(ids):
            cr.execute('select distinct parent_id from openstc_task_category where id IN %s',(tuple(ids),))
            ids = filter(None, map(lambda x:x[0], cr.fetchall()))
            if not level:
                return False
            level -= 1
        return True

    _constraints = [
        (_check_recursion, 'Error ! You cannot create recursive categories.', ['parent_id'])
    ]
    def child_get(self, cr, uid, ids):
        return [ids]

openstc_task_category()



class openstc_absent_type(osv.osv):
    _name = "openstc.absent.type"
    _description = ""
    _columns = {
            'name': fields.char('Affectation ', size=128, required=True),
            'code': fields.char('Code affectation', size=32, required=True),
            'description': fields.text('Description'),
    }
openstc_absent_type()

#----------------------------------------------------------
# Interventions
#----------------------------------------------------------


class project(osv.osv):
    _name = "project.project"
    _description = "Interventon stc"
    _inherit = "project.project"

    def _get_projects_from_tasks(self, cr, uid, task_ids, context=None):
        tasks = self.pool.get('project.task').browse(cr, uid, task_ids, context=context)
        project_ids = [task.project_id.id for task in tasks if task.project_id]
        return self.pool.get('project.project')._get_project_and_parents(cr, uid, project_ids, context)

    def _get_project_and_parents(self, cr, uid, ids, context=None):
        """ return the project ids and all their parent projects """
        res = set(ids)
        while ids:
            cr.execute("""
                SELECT DISTINCT parent.id
                FROM project_project project, project_project parent, account_analytic_account account
                WHERE project.analytic_account_id = account.id
                AND parent.analytic_account_id = account.parent_id
                AND project.id IN %s
                """, (tuple(ids),))
            ids = [t[0] for t in cr.fetchall()]
            res.update(ids)
        return list(res)

    #Overrides project : progress_rate ratio on planned_hours instead of 'total_hours'
    def _progress_rate(self, cr, uid, ids, names, arg, context=None):
        child_parent = self._get_project_and_children(cr, uid, ids, context)
        # compute planned_hours, total_hours, effective_hours specific to each project
        cr.execute("""
            SELECT project_id, COALESCE(SUM(planned_hours), 0.0),
                COALESCE(SUM(total_hours), 0.0), COALESCE(SUM(effective_hours), 0.0)
            FROM project_task WHERE project_id IN %s AND state <> 'cancelled'
            GROUP BY project_id
            """, (tuple(child_parent.keys()),))
        # aggregate results into res
        res = dict([(id, {'planned_hours':0.0,'total_hours':0.0,'effective_hours':0.0}) for id in ids])
        for id, planned, total, effective in cr.fetchall():
            # add the values specific to id to all parent projects of id in the result
            while id:
                if id in ids:
                    res[id]['planned_hours'] += planned
                    res[id]['total_hours'] += total
                    res[id]['effective_hours'] += effective
                id = child_parent[id]
        # compute progress rates
        for id in ids:
            if res[id]['planned_hours']:
                res[id]['progress_rate'] = round(100.0 * res[id]['effective_hours'] / res[id]['planned_hours'], 2)
            else:
                res[id]['progress_rate'] = 0.0
        return res


    def _tooltip(self, cr, uid, ids, myFields, arg, context):
        res = {}

        project_obj = self.pool.get('project.project')
        task_obj = self.pool.get('project.task')

        for id in ids:
            res[id] = ''
            inter = self.browse(cr, uid, id, context)
            if inter :
                first_date = None
                last_date = None
                allPlanned = True
                for task_id in inter.tasks :
                    task = task_obj.browse(cr, uid, task_id.id, context)
                    if  first_date == None :
                        first_date = task.date_start;
                    elif task.date_start and first_date>task.date_start :
                        first_date=task.date_start;

                    if last_date == None :
                        last_date = task.date_end;
                    elif task.date_end and last_date<task.date_end :
                        last_date=task.date_end

                    if task.state == 'draft' :
                        allPlanned = False

                if last_date :
                     last_date = fields.datetime.context_timestamp(cr, uid,
                            datetime.strptime(last_date, '%Y-%m-%d  %H:%M:%S')
                            , context)

                if first_date :
                     first_date = fields.datetime.context_timestamp(cr, uid,
                            datetime.strptime(first_date, '%Y-%m-%d  %H:%M:%S')
                            , context)


                if first_date :
                    if inter.progress_rate >= 100 :
                        res[id] = _(' Ended date ') + last_date.strftime(_("%A, %d %B %Y %H:%M").encode('utf-8')).decode('utf-8')
                    elif inter.progress_rate == 0 :
                        res[id] = _(' Scheduled start date ') + first_date.strftime(_("%A, %d %B %Y %H:%M").encode('utf-8')).decode('utf-8')

                    elif last_date and allPlanned:
                        res[id] = _(' Scheduled end date ') + last_date.strftime(_("%A, %d %B %Y %H:%M").encode('utf-8')).decode('utf-8')
                    else :
                        res[id] = _(' All tasks not planned ')

                if inter.state == 'cancelled' :
                    if inter.cancel_reason:
                      res[id] += inter.cancel_reason
                    else:
                      res[id] = _(' intervention cancelled ')

        return res


    def _overPourcent(self, cr, uid, ids, myFields, arg, context):
        res = {}

        project_obj = self.pool.get('project.project')
        task_obj = self.pool.get('project.task')

        for id in ids:
            res[id] = 0
            inter = self.browse(cr, uid, id, context)
            if inter :
                if inter.planned_hours :
                    res[id] = round(100.0 * inter.effective_hours / inter.planned_hours, 0);
        return res
    
    #if inter exists and is associated to a service, returns this service_id, else returns user services
    def get_services_authorized(self, cr, uid, id, context=None):
        if id:
            inter = self.browse(cr, uid, id, context=context)
            if inter.service_id:        
                return [inter.service_id.id]
            
        return self.pool.get("res.users").read(cr, uid, uid, ['service_ids'])['service_ids']
        
    
    def get_task_categ_authorized(self, cr, uid, id, context=None):
        service_ids = self.get_services_authorized(cr, uid, id, context=context)
        ret = []
        if service_ids:
            task_ids = self.pool.get("openstc.task.category").search(cr, uid, [('service_ids','in',service_ids)])
            ret = self.pool.get("openstc.task.category").read(cr, uid, task_ids, ['id','name'])
        return ret
    
    _actions = {
        'cancel':lambda self,cr,uid,record: record.state in ('open','scheduled'),
        'plan_unplan':lambda self,cr,uid,record: record.state == 'open' and not self.pool.get("project.task").search(cr, uid,[('state','=','draft'),('project_id','=',record.id)]),
        'add_task':lambda self,cr,uid,record: record.state in ('open','template'),
        'print': lambda self,cr,uid,record: True,
        'modify': lambda self,cr,uid,record: True,
        'create': lambda self,cr,uid,record: True,

        }
    def _get_actions(self, cr, uid, ids, myFields ,arg, context=None):
        #default value: empty string for each id
        ret = {}.fromkeys(ids,'')
        #evaluation of each _actions item, if test returns True, adds key to actions possible for this record
        for record in self.browse(cr, uid, ids, context=context):
            #ret.update({inter['id']:','.join([key for key,func in self._actions.items() if func(self,cr,uid,inter)])})
            ret.update({record.id:[key for key,func in self._actions.items() if func(self,cr,uid,record)]})
        return ret

    def _searchOverPourcent(self, cr, uid, obj, name, args, context=None):
        if args and len(args[0]) >= 2:
            arg = args[0]
            where = ''
            if arg[2] is False:
                where = 'planned_hours = 0 or effective_hours / planned_hours = 0'
            else:
                where = 'planned_hours > 0 and 100 * effective_hours / planned_hours %s %s' % (arg[1], arg[2])
            cr.execute('select id from %s where %s' % (self._table, where))
            ret = cr.fetchall()
            return [('id','in',[item[0] for item in ret])]
        return [('id','>',0)]

    _columns = {

        'ask_id': fields.many2one('openstc.ask', 'Demande', ondelete='set null', select="1", readonly=True),
        'create_uid': fields.many2one('res.users', 'Created by', readonly=True),
        'create_date' : fields.datetime('Create Date', readonly=True),
        'intervention_assignement_id':fields.many2one('openstc.intervention.assignement', 'Affectation'),
        'date_deadline': fields.date('Deadline',select=True),
        'site1': fields.many2one('openstc.site', 'Site principal'),
        'state': fields.selection([('closed', 'Closed'),('template', 'Template'),('open', 'Open'),('scheduled', 'Scheduled'),('pending', 'Pending'), ('closing', 'Closing'), ('cancelled', 'Cancelled')],
                                  'State', readonly=True, required=True, help=''),

        'service_id': fields.many2one('openstc.service', 'Service'),
        'description': fields.text('Description'),
        'site_details': fields.text('Précision sur le site'),
        'cancel_reason': fields.text('Cancel reason'),


        'progress_rate': fields.function(_progress_rate, multi="progress", string='Progress', type='float', group_operator="avg", help="Percent of tasks closed according to the total of tasks todo.",
            store = {
                'project.project': (_get_project_and_parents, ['tasks', 'parent_id', 'child_ids'], 9),
                'project.task': (_get_projects_from_tasks, ['planned_hours', 'remaining_hours', 'work_ids', 'state'], 19),
            }),

        'tooltip' : fields.function(_tooltip, method=True, string='Tooltip',type='char', store=False),
        'overPourcent' : fields.function(_overPourcent, fnct_search=_searchOverPourcent, method=True, string='OverPourcent',type='float', store=False),
        'actions':fields.function(_get_actions, method=True, string="Actions possibles",type="char", store=False),
    }

    #Overrides  set_template method of project module
    def set_template(self, cr, uid, ids, context=None):
        return True;

    def is_template(self, cr, uid, ids, context=None):
        if not(len(ids) == 1) : return false
        inter = self.pool.get('project.project').browse(cr, uid, ids[0], context=context)
        if isinstance(inter, browse_null)!= True :
            return inter.state == 'template' or False

    def _get_active_inter(self, cr, uid, context=None):
        if context is None:
            return False
        else:
            return context.get('active_id', False)

    def _get_ask(self, cr, uid, context=None):
        inter_id = self._get_active_inter(cr, uid, context)
        if inter_id :
            ask_id = self.pool.get('project.project').read(cr, uid, inter_id,['ask_id'],context)['ask_id']
            if ask_id :
                ask_id[0]
        return False

    #Cancel intervention from swif
    def cancel(self, cr, uid, ids, params, context=None):
        #print("test"+params)
        project_obj = self.pool.get(self._name)
        project = project_obj.browse(cr, uid, ids[0], context)
        task_obj = self.pool.get('project.task')
        ask_obj = self.pool.get('openstc.ask')

        #update intervention's tasks
        if _test_params(params, ['state','cancel_reason'])!= False:
            for task in project.tasks:
                 task_obj.write(cr, uid, [task.id], {
                    'state' : params['state'],
                    'user_id': None,
                    'team_id': None,
                    'date_end': None,
                    'date_start': None,
                }, context=context)

            #update intervention with cancel's reason
            project_obj.write(cr, uid, ids[0], {
                    'state' : params['state'],
                    'cancel_reason': params['cancel_reason'],
                }, context=context)

            ask_id = project.ask_id.id
            #update ask state of intervention
            if ask_id :
                ask_obj.write(cr, uid, ask_id , {
                            'state': 'closed',
                        }, context=context)
                #TODO uncomment
                #send_email(self, cr, uid, [ask_id], params, context=None)
        return True;

    _defaults = {
        'ask_id' : _get_ask,
    }

    _sql_constraints = [
        ('ask_uniq', 'unique(name,ask_id)', 'Demande déjà validée!'),
    ]

project()


class intervention_assignement(osv.osv):
    _name = "openstc.intervention.assignement"
    _description = ""
    _columns = {
            'name': fields.char('Affectation ', size=128, required=True),
            'code': fields.char('Code affectation', size=32, required=True),
            'asksAssigned': fields.one2many('openstc.ask', 'intervention_assignement_id', "asks"),
    }
intervention_assignement()

class project_work(osv.osv):
    _name = "project.task.work"
    _description = "Task work"
    _inherit = "project.task.work"

    _columns = {
        'manager_id': fields.related('ask_id', 'manager_id', type='many2one', string='Services'),
        'user_id': fields.many2one('res.users', 'Done by', required=False, select="1"),
        'team_id': fields.many2one('openstc.team', 'Done by', required=False, select="1"),
    }

project_work()


class project_task_type(osv.osv):
    _name = "project.task.type"
    _description = "project.task.type"
    _inherit = "project.task.type"

    _columns = {

    }

project_task_type()


class project_task_history(osv.osv):
    _name = 'project.task.history'
    _description = 'History of Tasks'
    _inherit = "project.task.history"

    _columns = {
        'state': fields.selection([('closed', 'Closed'),('absent', 'Absent'),('draft', 'New'),('open', 'In Progress'),('pending', 'Pending'), ('done', 'Done'), ('cancelled', 'Cancelled')], 'State'),

    }

project_task_history()

class project_vs_hours(osv.osv):
    _name = "project.vs.hours"
    _description = " Project vs  hours"
    _inherit = "project.vs.hours"

    _columns = {

    }

project_vs_hours()


class ask(osv.osv):
    _name = "openstc.ask"
    _description = "openstc.ask"
    _order = "create_date desc"

    def _get_user_service(self, cr, uid, ipurchase_orderds, fieldnames, name, args):
        return False


    def _get_uid(self, cr, uid, context=None):
        return uid

    def _get_services(self, cr, uid, context=None):
        user_obj = self.pool.get('res.users')
        return user_obj.read(cr, uid, uid, ['service_ids'],context)['service_ids']

    def _is_possible_action(self, cr, uid, ids, fields, arg, context):
        res = {}
        user_obj = self.pool.get('res.users')
        group_obj = self.pool.get('res.groups')

        for id in ids:
            res[id] = []
            isDST = False
            isManager = False

            asks = self.read(cr, uid, [id], ['intervention_ids','service_id','state'], context=context)
            user = user_obj.read(cr, uid, uid,
                                        ['groups_id','service_ids'],
                                        context)
            #user is DST (DIRECTOR group, code group=DIRE)?
            group_ids = group_obj.search(cr, uid, [('code','=','DIRE'),('id','in',user['groups_id'])])
            if len( group_ids ) != 0:
                isDST = True

            #user is Manager (code group = MANA)?
            group_ids = group_obj.search(cr, uid, [('code','in',('DIRE','MANA'))])
            if set(user['groups_id']).intersection(set(group_ids)) :
                isManager = True

            ask = asks[0] or False
            if isManager and ask and ask.has_key('intervention_ids')!=False and ask.has_key('service_id') and user.has_key('service_ids')!=False :
                if len(ask['intervention_ids'])==0 and ask['service_id'][0] in user['service_ids']:
                        if ask['state'] == 'wait' :
                            res[id] = ['valid', 'refused']
                            if isDST == False:
                                res[id] = ['valid', 'refused', 'confirm']

                        if ask['state'] == 'confirm' :
                            res[id] = ['valid', 'refused']

                        if ask['state'] == 'refused' :
                            res[id] = ['valid']
                            if isDST == False:
                                res[id] = ['valid', 'confirm']

        return res

#    def _is_valid_action(self, cr, uid, ids, fields, arg, context):
#        res = self._is_possible_action(cr, uid, ids, fields, arg, context)
#        for id in res:
#            asks = self.read(cr, uid, [id], ['state'], context=context)
#            ask = asks[0] or False
#            if ask['state'] in arg:
#                res[id] = True;
#        return res
#
#    def _is_request_confirm_action(self, cr, uid, ids, fields, arg, context):
#        res = self._is_possible_action(cr, uid, ids, fields, arg, context)
#        for id in res:
#            asks = self.read(cr, uid, [id], ['state'], context=context)
#            group_obj = self.pool.get('res.groups')
#            group_ids = group_obj.search(cr, uid, [('code','=','DIRECTOR')])
#            ask = asks[0] or False
#            if ask['state'] in arg and len(group_ids)>0 :
#                res[id] = True;
#        return res
#
#    def _is_refuse_action(self, cr, uid, ids, fields, arg, context):
#        res = self._is_possible_action(cr, uid, ids, fields, arg, context)
#        for id in res:
#            asks = self.read(cr, uid, [id], ['state'], context=context)
#            ask = asks[0] or False
#            if ask['state'] in arg:
#                res[id] = True;
#        return res

    def _tooltip(self, cr, uid, ids, myFields, arg, context):
        res = {}

        ask_obj = self.pool.get('openstc.ask')
        project_obj = self.pool.get('project.project')
        task_obj = self.pool.get('project.task')
        user_obj = self.pool.get('res.users')

        for id in ids:
            res[id] = ''


            ask = ask_obj.browse(cr, uid, id, context)
            if ask :
                modifyBy = user_obj.browse(cr, uid, ask.write_uid.id, context).name
                if ask.state == 'valid' or ask.state == 'closed' :
                    for intervention_id in ask.intervention_ids :
                         first_date = None
                         last_date = None
                         intervention = project_obj.browse(cr, uid, intervention_id.id, context)
                         if intervention :
                             for task_id in intervention.tasks :
                                 task = task_obj.browse(cr, uid, task_id.id, context)
                                 if task :
                                     if first_date == None:
                                        first_date = task.date_start
                                     elif task.date_start and first_date > task.date_start :
                                        first_date = task.date_start

                                     if last_date == None:
                                        last_date = task.date_end
                                     elif task.date_end and last_date < task.date_end :
                                        last_date = task.date_end
                             user = user_obj.browse(cr, uid, intervention.create_uid.id, context)
                             res[id] = _(" By ")  + user.name

                             if last_date :
                                 last_date = fields.datetime.context_timestamp(cr, uid,
                                                        datetime.strptime(last_date, '%Y-%m-%d  %H:%M:%S')
                                                        , context)

                             if first_date :
                                 first_date = fields.datetime.context_timestamp(cr, uid,
                                                        datetime.strptime(first_date, '%Y-%m-%d  %H:%M:%S')
                                                        , context)

                             if ask.state == 'closed' :
                                 if intervention.state == 'closed':
                                     res[id] += _(' Ended date ') + last_date.strftime(_("%A, %d. %B %Y %H:%M").encode('utf-8')).decode('utf-8')
                                 else:
                                      if intervention.cancel_reason:
                                          res[id] += intervention.cancel_reason
                                      else:
                                          res[id] = _(' intervention cancelled ')


                             elif first_date :
                                 if intervention.progress_rate == 0 :
                                     res[id] += _(' Scheduled start date ') + first_date.strftime(_("%A, %d. %B %Y %H:%M").encode('utf-8')).decode('utf-8')
                                 elif intervention.progress_rate == 100 :
                                     res[id] += _(' Ended date ') + last_date.strftime(_("%A, %d. %B %Y %H:%M").encode('utf-8')).decode('utf-8')
                                 elif last_date:
                                     res[id] += _(' Scheduled end date ') + last_date.strftime(_("%A, %d. %B %Y %H:%M").encode('utf-8')).decode('utf-8')
                                 else :
                                      res[id] += _(" To plan ")
                             else:
                                 res[id] += _(" Not plan ")

                elif ask.state == 'refused' :
                    if ask.refusal_reason:
                        res[id] = ask.refusal_reason  + '\n('+ modifyBy +')';
                    else:
                        res[id] = _(' request refused ')

                elif ask.state == 'confirm' :
                    if ask.note:
                        res[id] = ask.note + '\n('+ modifyBy +')';
                    else:
                        res[id] = _(' request confirmed ')


        return res

    _columns = {
        'name': fields.char('Asks wording', size=128, required=True, select=True),
        'create_date' : fields.datetime('Create Date', readonly=True, select=False),
        'create_uid': fields.many2one('res.users', 'Created by', readonly=True),
        'write_uid': fields.many2one('res.users', 'Created by', readonly=True),
        'current_date': fields.datetime('Date'),
        'confirm_by_dst': fields.boolean('Confirm by DST'),
        'description': fields.text('Description'),
        'intervention_ids': fields.one2many('project.project', 'ask_id', "Interventions", String="Interventions"),

        'partner_id': fields.many2one('res.partner', 'Partner', ondelete='set null'),
        'partner_address': fields.many2one('res.partner.address', 'Contact',ondelete='set null'),


        'partner_type': fields.many2one('openstc.partner.type', 'Partner Type', required=True),
        'partner_type_code': fields.char('Partner code', size=128),

        'partner_phone': fields.related('partner_address', 'phone', type='char', string='Téléphone'),
        'partner_email': fields.related('partner_address', 'email', type='char', string='Email'),

        'people_name': fields.char('Name', size=128),
        'people_phone': fields.char('Phone', size=10),
        'people_email': fields.char('Email', size=128),

        'intervention_assignement_id':fields.many2one('openstc.intervention.assignement', 'Affectation'),
        'site1': fields.many2one('openstc.site', 'Site principal'),
        'site_name': fields.related('site1', 'name', type='char', string='Site'),
        'site2': fields.many2one('openstc.site', 'Site secondaire'),
        'site3': fields.many2one('openstc.site', 'Place'),
        'site_details': fields.text('Précision sur le site'),
        'note': fields.text('Note'),
        'refusal_reason': fields.text('Refusal reason'),
        'manager_id': fields.many2one('res.users', 'Manager'),
        'partner_service_id': fields.related('partner_id', 'service_id', type='many2one', relation='openstc.service', string='Service du demandeur', help='...'),
        'service_id':fields.many2one('openstc.service', 'Service concerné'),
        'date_deadline': fields.date('Date souhaitée'),
        'state': fields.selection(_get_request_states, 'State', readonly=True,
                          help='If the task is created the state is \'Wait\'.\n If the task is started, the state becomes \'In Progress\'.\n If review is needed the task is in \'Pending\' state.\
                          \n If the task is over, the states is set to \'Done\'.'),

        'actions' : fields.function(_is_possible_action, method=True, string='Valider',type='selection', store=False),
        'tooltip' : fields.function(_tooltip, method=True, string='Tooltip',type='char', store=False),

    }


    _defaults = {
        'name' : lambda self, cr, uid, context : context['name'] if context and 'name' in context else None,
        'state': '',
        'current_date': lambda *a: datetime.now().strftime('%Y-%m-%d'),
        'actions': [],
    }


    def create(self, cr, uid, data, context={}):
        data['state'] = 'wait'
        manager_id = self.pool.get('openstc.service').read(cr, uid, data['service_id'],['manager_id'],context)['manager_id']
        if manager_id:
            data['manager_id'] = manager_id[0]

        res = super(ask, self).create(cr, uid, data, context)
        #TODO uncomment
        #send_email(self, cr, uid, [res], data, context)
        return res

    def write(self, cr, uid, ids, vals, context=None):
        isList = isinstance(ids, types.ListType)
        if isList == False :
            ids = [ids]
        res = super(ask, self).write(cr, uid, ids, vals, context=context)
        #if vals and vals.has_key('email_text'):
            #TODO uncomment
            #send_email(self, cr, uid, ids, vals, context)
        return res


    #valid ask from swif
    def valid(self, cr, uid, ids, params, context=None):
        ask_obj = self.pool.get(self._name)
        ask = ask_obj.browse(cr, uid, ids[0], context)
        project_obj = self.pool.get('project.project')
        task_obj = self.pool.get('project.task')

        #update ask with concerned service
        ask_obj.write(cr, uid, ids[0], {
                'state': params['request_state'],
                'description': params['description'],
                'intervention_assignement_id': params['intervention_assignement_id'],
                'service_id':  params['service_id'],
                'email_text': params['email_text'],
            }, context=context)

        #create intervention
        project_id = project_obj.create(cr, uid, {
                'ask_id': ask.id,
                'name': ask.name,
                'date_deadline': params['date_deadline'],
                'description': params['description'],
                'state': params['project_state'],
                'site1': params['site1'],
                'service_id':  params['service_id'],
            }, context=context)

        if params['create_task'] :
            #create task
            task_obj.create(cr, uid, {
                 'project_id': project_id,
                 'name': ask.name,
                 'planned_hours': params['planned_hours'],
                 'category_id': params['category_id'],
                }, context=context)
        #TODO : after configuration mail sender uncomment send_mail function
        #send_email(self, cr, uid, ids, params, context=None)
        return True


    def action_valid(self, cr, uid, ids, context=None):
        if context is None:
            context = {}

        document = self.browse(cr, uid, ids)[0]
        data_obj = self.pool.get('ir.model.data')
        form_view = data_obj.get_object_reference(cr, uid, 'openstc', 'view_openstc_ask_form2')
        action_id = self.pool.get('ir.actions.act_window').search(cr, uid, [("name", "=", "Intervention asks")], context=context)
        action_obj = self.pool.get('ir.actions.act_window').browse(cr, uid, action_id, context=context)[0]
        res = {}
        if action_obj:
            res = {
                'name' : 'Mentions',
                'view_type': 'form',
                'view_mode': 'form,tree',
                'res_id': int(document.id),
                'view_id': action_obj.view_id and [action_obj.view_id.id] or False,
                'views': [(form_view and form_view[1] or False, 'form')],
                'res_model': action_obj.res_model,
                'type': action_obj.type,
                'target': 'new',
                }
        return res


    def action_valid_ok(self, cr, uid, ids, context=None):
        self.write(cr, uid, ids, {'state': 'valid'}, context=context)
        this = self.browse(cr, uid, ids[0], context=context)
        intervention_obj = self.pool.get('project.project')
        intervention_id = intervention_obj.create(cr, uid, {
                #'qualifier_id': uid,
                'name': this.name or 'A completer',
                'date_deadline': this.date_deadline,
                #'user_id': this.intervention_manager.id,
                'site1': this.site1.id,
                'ask_id': this.id,
            }, context=context)


        data_obj = self.pool.get('ir.model.data')
        action_id = self.pool.get('ir.actions.act_window').search(cr, uid, [("name", "=", "Intervention asks")], context=context)
        action_obj = self.pool.get('ir.actions.act_window').browse(cr, uid, action_id, context=context)[0]
        res = {}
        if action_obj:
            res = {
                'view_mode': 'tree,form',
                'res_model': action_obj.res_model,
                'type': action_obj.type,
                }
        return res

    def action_to_be_confirm(self, cr, uid, ids, context=None):
         #TODO send email to DST
         return self.write(cr, uid, ids, {'state': 'confirm'}, context=context)

    def action_confirm(self, cr, uid, ids, context=None):
         #TODO send email to chef de service
         return self.write(cr, uid, ids, {'state': 'wait', 'confirm_by_dst': True}, context=context)

    def action_refused(self, cr, uid, ids, context=None):
        if context is None:
            context = {}
        mod_obj = self.pool.get('ir.model.data')
        act_obj = self.pool.get('ir.actions.act_window')
        result = mod_obj._get_id(cr, uid, 'openstc', 'action_openstc_refused_ask_view')
        if result:
            id = mod_obj.read(cr, uid, [result], ['res_id'])[0]['res_id']
        result = {}
        if not id:
            return result
        result = act_obj.read(cr, uid, [id], context=context)[0]
        result['target'] = 'new'
        return result

    def action_wait(self, cr, uid, ids, context=None):
        return self.write(cr, uid, ids, {'state': 'wait'}, context=context)

    def unlink(self, cr, uid, ids, context=None):
        for mydocument in self.browse(cr, uid, ids):
            if mydocument.intervention_ids!=None and len(mydocument.intervention_ids) > 0:
                raise osv.except_osv(_('Suppression Impossible !'),_('Des interventions sont liées à la demande'))
            else:
                return super(ask, self).unlink(cr, uid, ids, context=context)

    def onChangePartner(self, cr, uid, ids, partner_id, context=None):
        res = {}
        if partner_id :
            partner_obj = self.pool.get('res.partner')
            partner = partner_obj.browse(cr, uid, partner_id, context)
            addresses = partner_obj.address_get(cr, uid, [partner.id])
            res['value'] = {
                'partner_address': addresses['default'],
                'partner_phone' : partner.phone,
                'partner_email': partner.email,
                'site1': partner.technical_site_id.id,
                'service_id': partner.technical_service_id.id,
                'partner_service_id': partner.service_id.id,
            }
        else :
            res['value'] = {
                'partner_id' : False,
                'partner_address': False,
                'partner_phone' : '',
                'partner_email': '',
                'site1': False,
                'service_id': '',
                'partner_service_id': '',
            }
        return res

    def onChangePartnerType(self, cr, uid, ids, partner_type, context=None):
        res = {}
        partner_type_obj = self.pool.get('openstc.partner.type')
        partner_type_code = partner_type_obj.read(cr, uid, partner_type, ['code'],context)['code']

        if partner_type_code:
            res['partner_type_code'] = partner_type_code
            res['partner_id'] = False
            res['partner_address'] = None
            res['partner_phone'] = ''
            res['partner_email'] = ''
            res['site1'] = None
            res['service_id'] = ''
            res['partner_service_id'] = ''
        else:
            res['partner_id'] = False
            res['partner_address'] = None
            res['partner_phone'] = ''
            res['partner_email'] = ''
            res['site1'] = None
            res['service_id'] = ''
            res['partner_service_id'] = ''

        return {'value': res}

    def onChangePartnerAddress(self, cr, uid, ids, partner_address, context=None):
        res = {}
        if partner_address :
            partner_address_obj = self.pool.get('res.partner.address')
            partner_address = partner_address_obj.browse(cr, uid, partner_address, context)
            res['value'] = {
                'partner_phone' : partner_address.phone,
                'partner_email': partner_address.email,
            }
        else :
            res['value'] = {
                'partner_phone' : '',
                'partner_email': '',
            }
        return res

    def getNbRequestsTodo(self, cr, uid, users_id, filter=[], context=None):
        if not isinstance(users_id, list):
            users_id = [users_id]
        ret = {}
        for user in self.pool.get("res.users").browse(cr, uid, users_id, context=context):
            ret.update({str(user.id):0})
            #first, i get the code of user groups to filter easier
            groups = [group.code for group in user.groups_id if group.code]
            search_filter = []
            if 'DIRE' in groups:
                search_filter.extend([('state','=','confirm')])
            elif 'MANA' in groups:
                search_filter.extend([('state','=','wait')])
            #NOTE: if user is not DST nor Manager, returns all requests
            
            #launch search_count method adding optionnal filter defined in UI
            search_filter.extend(filter)
            ret[str(user.id)] = self.search_count(cr, user.id, search_filter, context=context)
        return ret


ask()


#----------------------------------------------------------
# Others
#----------------------------------------------------------

class openstc_planning(osv.osv):
    _name = "openstc.planning"
    _description = "Planning"

    _columns = {
        'name': fields.char('Planning', size=128),
    }

openstc_planning()


class todo(osv.osv):
    _name = "openstc.todo"
    _description = "todo stc"
    _rec_name = "title"

    _columns = {
            'title': fields.char('title', size=128),
            'completed': fields.boolean('Completed'),
    }
todo()