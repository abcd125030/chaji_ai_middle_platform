import { v4 as uuidv4 } from 'uuid';
import { siteConfig } from '@/lib/site-config';

const DB_NAME = siteConfig.dbName;
const STORE_NAME = 'files';

export interface FileRecord {
  id: string;
  name: string;
  type: string;
  data: string;
  size: number;
}

let db: IDBDatabase | null = null;

const getDb = (): Promise<IDBDatabase> => {
  return new Promise((resolve, reject) => {
    if (db) {
      return resolve(db);
    }

    const request = indexedDB.open(DB_NAME, 1);

    request.onerror = () => {
      reject('Error opening database');
    };

    request.onsuccess = () => {
      db = request.result;
      resolve(db);
    };

    request.onupgradeneeded = (event) => {
      const dbInstance = (event.target as IDBOpenDBRequest).result;
      if (!dbInstance.objectStoreNames.contains(STORE_NAME)) {
        dbInstance.createObjectStore(STORE_NAME, { keyPath: 'id' });
      }
    };
  });
};

export const initDB = async (): Promise<void> => {
  await getDb();
};

export const addFile = async (file: File): Promise<FileRecord> => {
  const db = await getDb();
  
  return new Promise((resolve, reject) => {
    const fileReader = new FileReader();
    
    fileReader.onload = (event) => {
      const fileData = event.target?.result as string;
      const newFile: FileRecord = {
        id: uuidv4(),
        name: file.name,
        type: file.type,
        data: fileData,
        size: file.size,
      };
      
      // 在FileReader回调内部创建事务
      const transaction = db.transaction([STORE_NAME], 'readwrite');
      const store = transaction.objectStore(STORE_NAME);
      const request = store.add(newFile);
      
      request.onsuccess = () => resolve(newFile);
      request.onerror = () => reject('Failed to add file');
    };
    
    fileReader.onerror = () => reject('Failed to read file');
    fileReader.readAsDataURL(file);
  });
};

export const getFiles = async (): Promise<FileRecord[]> => {
  const db = await getDb();
  const transaction = db.transaction([STORE_NAME], 'readonly');
  const store = transaction.objectStore(STORE_NAME);
  const request = store.getAll();

  return new Promise((resolve, reject) => {
    request.onsuccess = () => {
      resolve(request.result);
    };
    request.onerror = () => {
      reject('Failed to get files');
    };
  });
};

export const deleteFile = async (id: string): Promise<void> => {
  const db = await getDb();
  const transaction = db.transaction([STORE_NAME], 'readwrite');
  const store = transaction.objectStore(STORE_NAME);
  const request = store.delete(id);

  return new Promise((resolve, reject) => {
    request.onsuccess = () => resolve();
    request.onerror = () => reject('Failed to delete file');
  });
};