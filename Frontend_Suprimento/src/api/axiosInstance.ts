import axios from 'axios';
import {baseApiUrl} from '../../global';


const api = axios.create({
    baseURL: baseApiUrl,
})


export default api;
