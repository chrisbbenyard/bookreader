if (sessionStorage.askMode == null) {
  sessionStorage.askMode = 'yes'
  var appModeNote = $( "#appModeNote" );
  var body = $( document.body );
  if (
    ("standalone" in window.navigator) &&
    !window.navigator.standalone
    ){
    appModeNote.show();
    body.bind(
      "touchstart.appModeNote touchmove.appModeNote",
      function( event ){
        event.preventDefault();
        body.unbind( "touchstart.appModeNote touchmove.appModeNote" );
        appModeNote.fadeOut( 500 );
      }
    );
  }
}



