import React, {
	Component
} from 'react';
import PropTypes from 'prop-types';
import Simple3DScene from './Simple3DScene.js';

/**
 * Simple3DSceneComponent is intended to draw simple 3D scenes using the popular
 * Three.js scene graph library. In particular, the JSON representing the 3D scene
 * is intended to be human-readable, and easily generated via Python. In future, a
 * long-term approach would be to develop a library to generate Three.js JSON directly
 * inside Python to make this component redundant.
 */
export default class Simple3DSceneComponent extends Component {

	constructor(props) {
		super(props)
	}

	componentDidMount() {

	    this.scene = new Simple3DScene(this.props.data, this.mount, this.props.settings);
	    this.scene.toggleVisibility(this.props.toggleVisibility);

	}

	componentWillUpdate(nextProps, nextState) {

		if (nextProps.downloadRequest !== this.props.downloadRequest) {
		    this.scene.download(nextProps.downloadRequest.filename, nextProps.downloadRequest.filetype)
		}

		if (nextProps.data !== this.props.data) {
		    this.scene.addToScene(nextProps.data);
			this.scene.toggleVisibility(this.props.toggleVisibility)
		}

		if (nextProps.toggleVisibility !== this.props.toggleVisibility) {
			this.scene.toggleVisibility(nextProps.toggleVisibility)
		}

	}

	componentWillUnmount() {
	    this.scene.stop();
		this.mount.removeChild(this.scene.renderer.domElement);
	}

	render() {
		const {
			id
		} = this.props;

		return ( <div id={id}
		style = {
				{
					'width': '100%',
					'height': '100%'
				}
			}
			ref = {
				(mount) => {
					this.mount = mount
				}
			} >
			</div>
		);
	}
}


Simple3DSceneComponent.propTypes = {
	/**
	 * The ID used to identify this component in Dash callbacks
	 */
	id: PropTypes.string,

	/**
	 * Simple3DScene JSON
	 */
	data: PropTypes.object,

	/**
	 * Options used for generating scene
	 */
	settings: PropTypes.object,

    /**
	 * Hide/show nodes in scene by name (key), value is 1 to show the node
	 * and 0 to hide it
     */
    toggleVisibility: PropTypes.object,

    /**
	 * Increment to trigger a screenshot or scene download.
     */
    downloadRequest: PropTypes.object,

	/**
	 * Dash-assigned callback that should be called whenever any of the
	 * properties change
	 */
	setProps: PropTypes.func,

};
