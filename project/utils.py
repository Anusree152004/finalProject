from flask import request, url_for

def generate_breadcrumbs():
    path = request.path.strip('/').split('/')
    breadcrumbs = []
    for i in range(len(path)):
        name = path[i].replace('_', ' ').title()
        if i == len(path) - 1:
            breadcrumbs.append({'name': name, 'url': None})
        else:
            url = '/' + '/'.join(path[:i + 1])
            breadcrumbs.append({'name': name, 'url': url})
    return breadcrumbs