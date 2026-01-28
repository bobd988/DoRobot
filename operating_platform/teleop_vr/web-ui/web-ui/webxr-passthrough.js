// WebXR Passthrough Component for A-Frame
// Minimal implementation to prevent black screen without interfering with controls

AFRAME.registerComponent('webxr-passthrough', {
  schema: {
    referenceSpaceType: { type: 'string', default: 'local-floor' }
  },

  init: function () {
    console.log('WebXR Passthrough component initialized');
    const sceneEl = this.el.sceneEl;

    // Listen for WebXR session start
    sceneEl.addEventListener('enter-vr', () => {
      const xrSession = sceneEl.renderer.xr.getSession();

      if (xrSession) {
        console.log('WebXR Session started with blend mode:', xrSession.environmentBlendMode);

        // Only add minimal environment if in opaque mode (to prevent black screen)
        if (xrSession.environmentBlendMode === 'opaque') {
          this.addMinimalEnvironment();
        }
      }
    });
  },

  addMinimalEnvironment: function () {
    const sceneEl = this.el.sceneEl;

    // Check if environment already exists
    if (sceneEl.querySelector('#passthrough-env')) {
      return;
    }

    // Add only a simple dark gray background to prevent pure black screen
    // This won't interfere with controller tracking
    const sky = document.createElement('a-sky');
    sky.setAttribute('id', 'passthrough-env');
    sky.setAttribute('color', '#1a1a1a'); // Very dark gray instead of black
    sceneEl.appendChild(sky);

    console.log('WebXR Passthrough: Added minimal environment');
  }
});
