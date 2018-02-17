import random
import logging
import string
import os
import inspect
from shutit_module import ShutItModule

class shutit_auth(ShutItModule):


	def build(self, shutit):
		shutit.run_script('''#!/bin/bash
MODULE_NAME=shutit_auth
rm -rf $( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )/vagrant_run/*
if [[ $(command -v VBoxManage) != '' ]]
then
	while true
	do
		VBoxManage list runningvms | grep ${MODULE_NAME} | awk '{print $1}' | xargs -IXXX VBoxManage controlvm 'XXX' poweroff && VBoxManage list vms | grep shutit_auth | awk '{print $1}'  | xargs -IXXX VBoxManage unregistervm 'XXX' --delete
		# The xargs removes whitespace
		if [[ $(VBoxManage list vms | grep ${MODULE_NAME} | wc -l | xargs) -eq '0' ]]
		then
			break
		else
			ps -ef | grep virtualbox | grep ${MODULE_NAME} | awk '{print $2}' | xargs kill
			sleep 10
		fi
	done
fi
if [[ $(command -v virsh) ]] && [[ $(kvm-ok 2>&1 | command grep 'can be used') != '' ]]
then
	virsh list | grep ${MODULE_NAME} | awk '{print $1}' | xargs -n1 virsh destroy
fi
''')
		vagrant_image = shutit.cfg[self.module_id]['vagrant_image']
		vagrant_provider = shutit.cfg[self.module_id]['vagrant_provider']
		gui = shutit.cfg[self.module_id]['gui']
		memory = shutit.cfg[self.module_id]['memory']
		shutit.build['vagrant_run_dir'] = os.path.dirname(os.path.abspath(inspect.getsourcefile(lambda:0))) + '/vagrant_run'
		shutit.build['module_name'] = 'shutit_auth_' + ''.join(random.choice(string.ascii_letters + string.digits) for _ in range(6))
		shutit.build['this_vagrant_run_dir'] = shutit.build['vagrant_run_dir'] + '/' + shutit.build['module_name']
		shutit.send(' command rm -rf ' + shutit.build['this_vagrant_run_dir'] + ' && command mkdir -p ' + shutit.build['this_vagrant_run_dir'] + ' && command cd ' + shutit.build['this_vagrant_run_dir'])
		shutit.send('command rm -rf ' + shutit.build['this_vagrant_run_dir'] + ' && command mkdir -p ' + shutit.build['this_vagrant_run_dir'] + ' && command cd ' + shutit.build['this_vagrant_run_dir'])
		if shutit.send_and_get_output('vagrant plugin list | grep landrush') == '':
			shutit.send('vagrant plugin install landrush')
		shutit.send('vagrant init ' + vagrant_image)
		shutit.send_file(shutit.build['this_vagrant_run_dir'] + '/Vagrantfile','''Vagrant.configure("2") do |config|
  config.landrush.enabled = true
  config.vm.provider "virtualbox" do |vb|
    vb.gui = ''' + gui + '''
    vb.memory = "''' + memory + '''"
  end

  config.vm.define "auth1" do |auth1|
    auth1.vm.box = ''' + '"' + vagrant_image + '"' + '''
    auth1.vm.hostname = "auth1.vagrant.test"
    config.vm.provider :virtualbox do |vb|
      vb.name = "shutit_auth_1"
    end
  end
end''')
		try:
			pw = file('secret').read().strip()
		except IOError:
			pw = ''
		if pw == '':
			shutit.log("""You can get round this manual step by creating a 'secret' with your password: 'touch secret && chmod 700 secret'""",level=logging.CRITICAL)
			pw = shutit.get_env_pass()
			import time
			time.sleep(10)

		try:
			shutit.multisend('vagrant up --provider ' + shutit.cfg['shutit-library.virtualization.virtualization.virtualization']['virt_method'] + " auth1",{'assword for':pw,'assword:':pw},timeout=99999)
		except NameError:
			shutit.multisend('vagrant up auth1',{'assword for':pw,'assword:':pw},timeout=99999)
		if shutit.send_and_get_output("""vagrant status 2> /dev/null | grep -w ^auth1 | awk '{print $2}'""") != 'running':
			shutit.pause_point("machine: auth1 appears not to have come up cleanly")


		# machines is a dict of dicts containing information about each machine for you to use.
		machines = {}
		machines.update({'auth1':{'fqdn':'auth1.vagrant.test'}})
		ip = shutit.send_and_get_output('''vagrant landrush ls 2> /dev/null | grep -w ^''' + machines['auth1']['fqdn'] + ''' | awk '{print $2}' ''')
		machines.get('auth1').update({'ip':ip})



		for machine in sorted(machines.keys()):
			shutit.login(command='vagrant ssh ' + machine,check_sudo=False)
			shutit.login(command='sudo su -',password='vagrant',check_sudo=False)
			shutit.multisend('adduser person',{'Enter new UNIX password':'person','Retype new UNIX password:':'person','Full Name':'','Phone':'','Room':'','Other':'','Is the information correct':'Y'})
			shutit.logout()
			shutit.logout()
			shutit.login(command='vagrant ssh ' + sorted(machines.keys())[0],check_sudo=False)
			shutit.login(command='sudo su -',password='vagrant',check_sudo=False)

			################################################################################
			# LDAP
			################################################################################
			# https://help.ubuntu.com/lts/serverguide/openldap-server.html
			# TODO: set up people, oauth, saml
			shutit.install('slapd ldap-utils')
			#shutit.pause_point(' https://unix.stackexchange.com/questions/96215/feeding-input-values-to-dpkg-reconfigure-in-a-non-interactive-way')
			shutit.send('dpkg-reconfigure -fnoninteractive slapd')
			# https://www.digitalocean.com/community/tutorials/how-to-change-account-passwords-on-an-openldap-server
			password = '12345'
			shutit.send_file('newpasswd.ldif','''
dn: olcDatabase={1}mdb,cn=config
changetype: modify
replace: olcRootPW
olcRootPW: {SSHA}iGjncj1i1qaTGtWYv58KYzJ+mmTONUBT''')
			shutit.send('ldapmodify -H ldapi:// -Y EXTERNAL -f newpasswd.ldif')
			shutit.send('ldapsearch -x -LLL -H ldap:/// -b dc=vagrant,dc=test dn')
			shutit.send_file('add_content.ldif','''dn: ou=People,dc=vagrant,dc=test
objectClass: organizationalUnit
ou: People

dn: ou=Groups,dc=vagrant,dc=test
objectClass: organizationalUnit
ou: Groups

dn: cn=miners,ou=Groups,dc=vagrant,dc=test
objectClass: posixGroup
cn: miners
gidNumber: 5000

dn: uid=john,ou=People,dc=vagrant,dc=test
objectClass: inetOrgPerson
objectClass: posixAccount
objectClass: shadowAccount
uid: john
sn: Doe
givenName: John
cn: John Doe
displayName: John Doe
uidNumber: 10000
gidNumber: 5000
userPassword: johnldap
gecos: John Doe
loginShell: /bin/bash
homeDirectory: /home/john''')
			shutit.multisend('ldapadd -x -D cn=admin,dc=vagrant,dc=test -W -f add_content.ldif',{'ass':password})
			shutit.send("ldapsearch -x -LLL -b dc=vagrant,dc=test 'uid=john' cn gidNumber")

			shutit.send("ldapsearch -Q -LLL -Y EXTERNAL -H ldapi:/// -b cn=config '(olcDatabase={1}mdb)' olcAccess # acl of mdb database")
			shutit.send("ldapsearch -Q -LLL -Y EXTERNAL -H ldapi:/// -b cn=config '(olcDatabase={0}config)' olcAccess # the acl config db")
			shutit.send("ldapsearch -Q -LLL -Y EXTERNAL -H ldapi:/// -b cn=config '(olcAccess=*)' olcAccess olcSuffix # all the acls")
			shutit.send_file('logging.ldif','''dn: cn=config
changetype: modify
replace: olcLogLevel
olcLogLevel: stats''')
			shutit.send('ldapmodify -Q -Y EXTERNAL -H ldapi:/// -f logging.ldif')
			# in this verbose mode your host's syslog engine (rsyslog) may have a hard time keeping up and may drop messages:

			# rsyslogd-2177: imuxsock lost 228 messages from pid 2547 due to rate-limiting
			# You may consider a change to rsyslog's configuration. In /etc/rsyslog.conf, put:
			# 
			# # Disable rate limiting
			# # (default is 200 messages in 5 seconds; below we make the 5 become 0)
			# $SystemLogRateLimitInterval 0
			# and restart the daemon

			# TLS: skipped - note you do not need ldaps://!
			# LDAP over TLS/SSL (ldaps://) is deprecated in favour of StartTLS. The latter refers to an existing LDAP session (listening on TCP port 389) becoming protected by TLS/SSL whereas LDAPS, like HTTPS, is a distinct encrypted-from-the-start protocol that operates over TCP port 636.

			#LDAPAUTH
			#shutit.install('libnss-ldap')
			shutit.multisend('DEBIAN_FRONTEND=text apt install -y libnss-ldap',{'LDAP server Uniform Resource Identifier':'ldap://localhost:389','Distinguished name of the search base:':'dc=vagrant,dc=test','LDAP version to use:':'3','Make local root Database admin:':'no','Does the LDAP database require login':'no'})
			shutit.send('auth-client-config -t nss -p lac_ldap')
#   44  vi /etc/ldapscripts/ldapscripts.conf 
			shutit.multisend('DEBIAN_FRONTEND=text pam-auth-update',{'PAM profiles to enable:':'1 2 3 4'})
			shutit.install('ldapscripts')
			shutit.send('''cat >  /etc/ldapscripts/ldapscripts.conf << END
SERVER=localhost
BINDDN='cn=admin,dc=vagrant,dc=test'
BINDPWDFILE="/etc/ldapscripts/ldapscripts.passwd"
SUFFIX='dc=vagrant,dc=test'
GSUFFIX='ou=Groups'
USUFFIX='ou=People'
MSUFFIX='ou=Computers'
GIDSTART=10000
UIDSTART=10000
MIDSTART=10000
END''')
			shutit.send('''sh -c "echo -n '12345' > /etc/ldapscripts/ldapscripts.passwd"''')
			shutit.send('chmod 400 /etc/ldapscripts/ldapscripts.passwd')
   			shutit.send('ldapadduser george root')
			# Workaround: https://ubuntuforums.org/showthread.php?t=1488232
			shutit.send('''cat > /usr/share/ldapscripts/runtime.debian << END
# Various binaries used within scripts
LDAPSEARCHBIN=`which ldapsearch`
LDAPADDBIN=`which ldapadd`
LDAPDELETEBIN=`which ldapdelete`
LDAPMODIFYBIN=`which ldapmodify`
LDAPMODRDNBIN=`which ldapmodrdn`
LDAPPASSWDBIN=`which ldappasswd`
END''')
   			shutit.multisend('ldapsetpasswd george',{'New Password':'12345'})
			shutit.login('ssh george@localhost',password='12345')
			shutit.logout()
			################################################################################
			# SAML - but what is it? Just an authentication method?
			# https://en.wikipedia.org/wiki/Security_Assertion_Markup_Language
			# https://en.wikipedia.org/wiki/Security_Assertion_Markup_Language#/media/File:Saml2-browser-sso-redirect-post.png
			# SAML vs OAUTH: https://dzone.com/articles/saml-versus-oauth-which-one
			# https://www.digitalocean.com/community/tutorials/how-to-install-and-configure-simplesamlphp-for-saml-authentication-on-ubuntu-16-04
			################################################################################
			
			shutit.logout()
			shutit.logout()
		return True


	def get_config(self, shutit):
		shutit.get_config(self.module_id,'vagrant_image',default='ubuntu/xenial64')
		shutit.get_config(self.module_id,'vagrant_provider',default='virtualbox')
		shutit.get_config(self.module_id,'gui',default='false')
		shutit.get_config(self.module_id,'memory',default='1024')
		return True

	def test(self, shutit):
		return True

	def finalize(self, shutit):
		return True

	def is_installed(self, shutit):
		return False

	def start(self, shutit):
		return True

	def stop(self, shutit):
		return True

def module():
	return shutit_auth(
		'bash_awesome_feb_2018.shutit_auth.shutit_auth', 1756268995.0001,
		description='',
		maintainer='',
		delivery_methods=['bash'],
		depends=['shutit.tk.setup','shutit-library.virtualization.virtualization.virtualization','tk.shutit.vagrant.vagrant.vagrant']
	)
