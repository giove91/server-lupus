function toggle_comments(id, heading_id) {
    var element = document.getElementById(id);
    var heading_element = document.getElementById(heading_id);
    
    if ( element.style.display === 'block' ) {
        element.style.display = 'none';
        heading_element.innerHTML = 'Visualizza i commenti';
    }
    else {
        element.style.display = 'block';
        heading_element.innerHTML = 'Nascondi i commenti';
    }
    
    
}
