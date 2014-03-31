
speed = 3.0;

function create_fish(name) {
    var fish_id = 'fish_' + name;
    var image = fish_images[Math.floor(Math.random() * fish_images.length)];
    $('body').append('<div id="' + fish_id + '" class="fish"><object type="image/svg+xml" data="' + image + '"></object></div>');
    var width = $(window).width() + $('#'+fish_id).width();
    var height = $(window).height() + $('#'+fish_id).height();
    var x = Math.random() * width - $('#'+fish_id).width();
    var y = Math.random() * height - $('#'+fish_id).height();
    var deltax = speed * (Math.random() - 0.5);
    var deltay = speed * (Math.random() - 0.5);
    $('#'+fish_id).css('top', y);
    $('#'+fish_id).css('left', x);
    $('#'+fish_id).css('display', 'block');
    setInterval(
        function() {
            if (x < -$('#'+fish_id).width() || x > $(window).width() ||
               y < -$('#'+fish_id).height() || y > $(window).height()) {
                deltax = speed * (Math.random() - 0.5);
                deltay = speed * (Math.random() - 0.5);
            }
            x += deltax;
            y += deltay;
            $('#'+fish_id).css('top', y);
            $('#'+fish_id).css('left', x);
        }, 150);
}

function create_fishes(num) {
    var i;
    for (i = 0; i < num; i++) {
        create_fish(i);
    }
}

function create_fishes_by_density(density) {
    var num = $(window).width() * $(window).height() * density;
    create_fishes(num);
}
