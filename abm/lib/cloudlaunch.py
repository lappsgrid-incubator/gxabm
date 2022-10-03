import os
import json
import arrow
import requests
import configparser

from common import Context
from cloudlaunch_cli.main import create_api_client


def list(context: Context, args: list):
    archived = False
    filter = None
    status = lambda t: t.instance_status if t.instance_status else t.status
    while len(args) > 0:
        arg = args.pop(0)
        if arg in ['-a', '--archived', 'archived']:
            archived = True
        elif arg in ['-r', '--running', 'running']:
            filter = lambda d: 'running' in status(d.latest_task)
        elif arg in ['-d', '--deleted', 'deleted']:
            filter = lambda d: 'DELETE' in d.latest_task.action
        elif arg in ['-l', '--launch', 'launch']:
            filter = lambda d: 'LAUNCH' in d.latest_task.action
        else:
            print(f"Invalid parameter: ${arg}")
            return
    deployments = create_api_client().deployments.list(archived=archived)

    if filter is not None:
        deployments = [ d for d in deployments if filter(d) ]
    _print_deployments(deployments)



def create(context: Context, args: list):
    cloud = None
    params = {
        'application': 'cloudman-20',
        'application_version': 'dev'
    }
    config = {
        "config_cloudlaunch": {
            "rootStorageType": "volume",
            "rootStorageSize": 42,
            "keyPair": ""
        },
        "config_cloudman2": {
            "clusterPassword": "gvl_letmein"
        }
    }
    targets = {
        'aws': 11,
        'gcp': 16
    }
    while len(args) > 0:
        arg = args.pop(0)
        if arg in ['aws', 'gcp']:
            if cloud is not None:
                print(f"ERROR: the cloud provider has already been specified: {cloud}")
                return
            cloud = arg
            params['deployment_target_id'] = targets[cloud]
        elif arg in ['-c', '--config']:
            filepath = args.pop(0)
            with open(filepath, 'r') as f:
                params['config_app'] = json.load(f)
        elif arg in ['-t', '--type']:
            config['config_cloudlaunch']['vmType'] = args.pop(0)
        elif arg in ['-k', '--kp', '--keypair']:
            config['config_cloudlaunch']['keyPair'] = args.pop(0)
        elif arg in ['-p', '--password']:
            config['config_cloudman2']['clusterPassword'] = args.pop(0)
        elif 'name' in params:
            print(f"ERROR: the cluster name has already been specified: {params['name']}")
            return
        else:
            params['name'] = arg

    params['config_app'] = config
    if 'name' not in params:
        print("ERROR: cluster name not specifed")
        return
    if cloud is None:
        print("ERROR: cloud provider not specied. Must be one of 'aws' or 'gcp'")
        return
    if 'vmType' not in config['config_cloudlaunch']:
        print("ERROR: please specify a VM type.")
        return
    cloudlaunch_client = create_api_client(cloud)
    new_deployment = cloudlaunch_client.deployments.create(**params)
    _print_deployments([new_deployment])


def delete(context: Context, args: list):
    if len(args) != 1:
        print("ERROR: Invalid parameters.")
        return
    # if args[0] not in ['aws', 'gcp']:
    #     print(f"ERROR: Invalid cloud specified: '{args[0]}'. Must be one of 'aws' or 'gcp'.")
    #     return
    id = args[0]
    configfile = os.path.expanduser("~/.cloudlaunch")
    if not os.path.exists(configfile):
        print("ERROR: Cloudlaunch has not been configured.")
        return

    config = configparser.ConfigParser()
    config.read(configfile)

    #cloudlaunch_client = create_api_client(args[0])
    #cloudlaunch_client.deployments.delete(args[1])
    url = config['cloudlaunch-cli']['url']
    token = config['cloudlaunch-cli']['token']
    headers = {
        'Accept': 'application/json',
        'Content-type': 'application/json',
        'Authorization': f"Token {token}"
    }

    data = dict(action='DELETE')
    print(f"URL is: {url}/deployments/{id}/tasks/")
    response = requests.post(f"{url}/deployments/{id}/tasks/", json=data, headers=headers)
    if response.status_code < 300:
        print(f"Deleted deployment {id}")
    else:
        print(f"{response.status_code} - {response.reason}")
        print(response.text)

def _print_deployments(deployments):
    if len(deployments) > 0:
        print("{:6s}  {:24s}  {:6s}  {:15s}  {:15s} {:s}".format(
            "ID", "Name", "Cloud", "Created", "Address", "Status"))
    else:
        print("No deployments.")
    for deployment in deployments:
        created_date = arrow.get(deployment.added)
        latest_task = deployment.latest_task
        latest_task_status = latest_task.instance_status \
            if latest_task.instance_status else latest_task.status
        latest_task_display = "{action}:{latest_task_status}".format(
            action=latest_task.action,
            latest_task_status=latest_task_status)
        ip_address = deployment.public_ip if deployment.public_ip else 'N/A'
        cloud = deployment._data['deployment_target']['target_zone']['cloud']['id']
        print("{identifier:6d}  {name:24.24s}  {cloud:6.6s}  {created_date:15.15s}  "
              "{ip_address:15.15s} {latest_task_display}".format(
                  identifier=deployment._id, cloud=cloud,
                  created_date=created_date.humanize(),
                  latest_task_display=latest_task_display,
                  ip_address=ip_address, **deployment._data))
        #pprint(deployment._data)
        #print()