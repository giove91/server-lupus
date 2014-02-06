from game.models import *

def setup_roles():
    p = Team(team_name='Popolani')
    l = Team(team_name='Lupi')
    n = Team(team_name='Negromanti')
    p.save()
    l.save()
    n.save()
    
    Role.objects.create(
        role_name='Contadino',
        team=p,
        has_power=False,
    )
    
    Role.objects.create(
        role_name='Cacciatore',
        team=p,
        on_living=True,
        on_dead=False,
    )
    
    Role.objects.create(
        role_name='Custode del cimitero',
        team=p,
        on_living=False,
        on_dead=True,
        reusable_on_same_target=False,
    )
    
    Role.objects.create(
        role_name='Divinatore',
        team=p,
        has_power=False,
    )
    
    Role.objects.create(
        role_name='Esorcista',
        team=p,
        is_mystic=True,
        reflexive=True,
    )
    
    Role.objects.create(
        role_name='Espansivo',
        team=p,
        frequency=2,
        on_living=True,
        on_dead=False,
    )
    
    Role.objects.create(
        role_name='Guardia del corpo',
        team=p,
        on_living=True,
        on_dead=False,
    )
    
    Role.objects.create(
        role_name='Investigatore',
        team=p,
        on_living=False,
        on_dead=True,
    )
    
    Role.objects.create(
        role_name='Mago',
        team=p,
        is_mystic=True
    )
    
    Role.objects.create(
        role_name='Massone',
        team=p,
        has_power=False,
    )
    
    Role.objects.create(
        role_name='Messia',
        team=p,
        is_mystic=True,
        frequency=0,
        on_living=False,
        on_dead=True,
    )
    
    Role.objects.create(
        role_name='Necrofilo',
        team=p,
        frequency=0,
        on_living=False,
        on_dead=True,
    )
    
    Role.objects.create(
        role_name='Stalker',
        team=p,
        frequency=2,
        on_living=True,
        on_dead=False,
    )
    
    Role.objects.create(
        role_name='Veggente',
        team=p,
        is_mystic=True,
        on_living=True,
        on_dead=False,
    )
    
    Role.objects.create(
        role_name='Voyeur',
        team=p,
        frequency=2,
    )


def setup_game():
    Game.objects.create()


def setup_dummy_players():
    g = Game.objects.get()
    users = User.objects.all()
    for user in users:
        Player.objects.create(user=user, game=g)
    
